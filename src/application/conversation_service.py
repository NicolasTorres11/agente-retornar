"""Conversation orchestration use case for the local agent."""

from src.classifier import Action, Category, ClassificationResult, classify
from src.domain.models import FlowState, InboundMessage, OutboundMessage, Priority, ProcessOutcome
from src.ports.messaging import OutboundMessenger
from src.ports.repository import ConversationRepository

CONSENT_REQUEST = (
    "Hola, soy el asistente virtual de Clinica Retornar. Para atender tu solicitud "
    "necesito tu autorizacion para tratar tus datos personales. "
    "Responde SI AUTORIZO para continuar o NO para finalizar."
)
CONSENT_ACCEPTED = "Gracias. Tu autorizacion fue registrada. En que podemos ayudarte hoy?"
CONSENT_REJECTED = "Entendido. No continuaremos con la atencion automatica."
CRISIS_RESPONSE = (
    "Lo que me cuentas es muy importante. Te conectaremos con un profesional de salud mental. "
    "Si sientes que tu vida esta en riesgo, llama ahora a la Linea 106 en Bogota o al 123 "
    "si hay peligro inmediato."
)
HANDOFF_RESPONSE = (
    "He registrado tu solicitud para revision por una persona de nuestro equipo. "
    "Te contactaremos por este canal."
)


class ConversationService:
    def __init__(self, repository: ConversationRepository, messenger: OutboundMessenger) -> None:
        self.repository = repository
        self.messenger = messenger

    async def process(self, message: InboundMessage) -> ProcessOutcome:
        if not await self.repository.record_inbound(message):
            return ProcessOutcome(status="duplicate", responses=[])

        result = classify(message.text)
        await self.repository.record_classification(message.message_id, result)

        # Safety screening precedes consent for first-contact emergencies.
        if result.suggested_action == Action.ESCALAR_CRISIS:
            await self.repository.set_state(message.wa_id, FlowState.CRISIS_ACTIVE)
            await self.repository.record_escalation(
                message.wa_id, "risk_detected", Priority.CRITICAL, result
            )
            await self._respond(message.wa_id, CRISIS_RESPONSE)
            return ProcessOutcome("crisis_escalated", [CRISIS_RESPONSE], result)

        if not await self.repository.has_consent(message.wa_id):
            normalized = message.text.lower().strip()
            if "si autorizo" in normalized or "sí autorizo" in normalized:
                await self.repository.record_consent(message.wa_id, True)
                await self._respond(message.wa_id, CONSENT_ACCEPTED)
                return ProcessOutcome("consent_accepted", [CONSENT_ACCEPTED], result)
            if normalized == "no" or "no autorizo" in normalized:
                await self.repository.record_consent(message.wa_id, False)
                await self._respond(message.wa_id, CONSENT_REJECTED)
                return ProcessOutcome("consent_rejected", [CONSENT_REJECTED], result)
            await self.repository.set_state(message.wa_id, FlowState.AWAITING_CONSENT)
            await self._respond(message.wa_id, CONSENT_REQUEST)
            return ProcessOutcome("consent_requested", [CONSENT_REQUEST], result)

        response, state, priority = self._route(result)
        if priority:
            await self.repository.record_escalation(
                message.wa_id, result.suggested_action.value, priority, result
            )
        await self.repository.set_state(message.wa_id, state)
        if response:
            await self._respond(message.wa_id, response)
        return ProcessOutcome("processed", [response] if response else [], result)

    def _route(self, result: ClassificationResult) -> tuple[str | None, FlowState, Priority | None]:
        if result.category == Category.SOLICITUD_CITA:
            return (
                "Con gusto te ayudo a gestionar tu cita. "
                "Indica especialidad, EPS y si es de control.",
                FlowState.IN_PROGRESS,
                None,
            )
        if result.category == Category.INFO_ADMINISTRATIVA:
            return (
                "Recibi tu consulta administrativa. "
                "Nuestro equipo confirmara la informacion requerida.",
                FlowState.IN_PROGRESS,
                None,
            )
        if result.category == Category.CONSULTA_CLINICA:
            return HANDOFF_RESPONSE, FlowState.HANDOFF, Priority.URGENT
        if result.category == Category.PQR:
            return HANDOFF_RESPONSE, FlowState.HANDOFF, Priority.NORMAL
        if result.suggested_action == Action.ESCALAR_HUMANO:
            return HANDOFF_RESPONSE, FlowState.HANDOFF, Priority.NORMAL
        if result.suggested_action == Action.IGNORAR:
            return None, FlowState.IN_PROGRESS, None
        return (
            "Hola. Puedo ayudarte con citas o informacion administrativa.",
            FlowState.IN_PROGRESS,
            None,
        )

    async def _respond(self, wa_id: str, text: str) -> None:
        local_id = await self.repository.queue_outbound(wa_id, text)
        try:
            meta_id = await self.messenger.send(OutboundMessage(wa_id=wa_id, text=text))
            await self.repository.mark_outbound_sent(local_id, meta_id)
        except Exception as exc:
            await self.repository.mark_outbound_failed(local_id, str(exc))
            raise
