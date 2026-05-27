"""Conversation orchestration use case for the local agent."""

import re
import unicodedata
from datetime import date, timedelta

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
APPOINTMENT_PROMPT_PREFIX = "Con gusto te ayudo a gestionar tu cita."
APPOINTMENT_SLOTS = ("tipo_cita", "especialidad", "eps", "urgencia")


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

        appointment = await self.repository.get_open_appointment(message.wa_id)
        appointment_pending = appointment is not None or await self._has_pending_appointment_prompt(
            message.wa_id
        )
        if (
            result.category == Category.SOLICITUD_CITA
            and result.suggested_action == Action.ESCALAR_HUMANO
            and not appointment_pending
        ):
            await self.repository.record_escalation(
                message.wa_id, result.suggested_action.value, Priority.NORMAL, result
            )
            await self.repository.set_state(message.wa_id, FlowState.HANDOFF)
            await self._respond(message.wa_id, HANDOFF_RESPONSE)
            return ProcessOutcome("processed", [HANDOFF_RESPONSE], result)
        if result.category == Category.SOLICITUD_CITA or appointment_pending:
            if appointment is None:
                appointment = (
                    await self._recover_appointment_slots(message.wa_id)
                    if appointment_pending
                    else {}
                )
            response, state, priority = await self._appointment_response(message, appointment)
            if priority:
                await self.repository.record_escalation(
                    message.wa_id, "urgent_appointment", priority, result
                )
            await self.repository.set_state(message.wa_id, state)
            await self._respond(message.wa_id, response)
            return ProcessOutcome("processed", [response], result)

        response, state, priority = self._route(result, message.text)
        if priority:
            await self.repository.record_escalation(
                message.wa_id, result.suggested_action.value, priority, result
            )
        await self.repository.set_state(message.wa_id, state)
        if response:
            await self._respond(message.wa_id, response)
        return ProcessOutcome("processed", [response] if response else [], result)

    def _route(
        self, result: ClassificationResult, message_text: str
    ) -> tuple[str | None, FlowState, Priority | None]:
        if result.category == Category.INFO_ADMINISTRATIVA:
            return (
                self._administrative_response(message_text),
                FlowState.IN_PROGRESS,
                None,
            )
        if result.category == Category.CONSULTA_CLINICA:
            return (
                "Tu mensaje requiere revision de un profesional clinico. "
                "No puedo recomendar cambios de medicacion ni valorar sintomas por este medio. "
                "He registrado el caso para atencion prioritaria.",
                FlowState.HANDOFF,
                Priority.URGENT,
            )
        if result.category == Category.PQR:
            return (
                "Lamentamos el inconveniente. He registrado tu solicitud como PQR para "
                "revision del equipo de atencion al usuario. La respuesta formal tiene un "
                "plazo maximo de 15 dias habiles.",
                FlowState.HANDOFF,
                Priority.NORMAL,
            )
        if result.suggested_action == Action.ESCALAR_HUMANO:
            return HANDOFF_RESPONSE, FlowState.HANDOFF, Priority.NORMAL
        if result.suggested_action == Action.IGNORAR:
            return None, FlowState.IN_PROGRESS, None
        return (
            "Hola. Puedo ayudarte con citas o informacion administrativa.",
            FlowState.IN_PROGRESS,
            None,
        )

    async def _appointment_response(
        self, message: InboundMessage, stored_slots: dict[str, str]
    ) -> tuple[str, FlowState, Priority | None]:
        if stored_slots.get("_status") == "requested":
            slots = {key: value for key, value in stored_slots.items() if key != "_status"}
            await self.repository.save_appointment(
                message.wa_id, slots, status="awaiting_selection"
            )
            return (
                self._appointment_availability_response(slots),
                FlowState.AWAITING_APPOINTMENT_SLOT,
                None,
            )
        if stored_slots.get("_status") == "awaiting_selection":
            selection = self._appointment_selection(message.text)
            if not selection:
                return (
                    "Para confirmar la cita de demostracion, responde Opcion 1, "
                    "Opcion 2 u Opcion 3.",
                    FlowState.AWAITING_APPOINTMENT_SLOT,
                    None,
                )
            appointment = self._appointment_availability()[selection - 1]
            await self.repository.save_appointment(message.wa_id, stored_slots, status="scheduled")
            return (
                "Cita de demostracion confirmada: "
                f"{stored_slots['especialidad']} - {appointment}. "
                "Este agendamiento es simulado para la prueba local.",
                FlowState.APPOINTMENT_SCHEDULED,
                None,
            )

        slots = {**stored_slots, **self._extract_appointment_slots(message.text)}
        slots.pop("_status", None)
        missing = [slot for slot in APPOINTMENT_SLOTS if slot not in slots]
        if missing:
            await self.repository.save_appointment(message.wa_id, slots)
            questions = {
                "tipo_cita": "si es cita de control o de primera vez",
                "especialidad": "especialidad",
                "eps": "EPS",
                "urgencia": "si tu solicitud es urgente o no urgente",
            }
            required = ", ".join(questions[slot] for slot in missing)
            recorded = self._appointment_recorded_text(slots)
            prefix = f"Ya registre {recorded}. " if recorded else f"{APPOINTMENT_PROMPT_PREFIX} "
            return (
                f"{prefix}Indica {required}.",
                FlowState.AWAITING_APPOINTMENT_INFO,
                None,
            )

        if slots["urgencia"] == "Urgente":
            await self.repository.save_appointment(message.wa_id, slots, status="urgent_handoff")
            return (
                "Registre tu solicitud como urgente. Una persona del equipo de "
                "agendamiento la revisara con prioridad para asignarte atencion adecuada.",
                FlowState.HANDOFF,
                Priority.URGENT,
            )

        await self.repository.save_appointment(message.wa_id, slots, status="awaiting_selection")
        return (
            self._appointment_availability_response(slots),
            FlowState.AWAITING_APPOINTMENT_SLOT,
            None,
        )

    async def _recover_appointment_slots(self, wa_id: str) -> dict[str, str]:
        slots: dict[str, str] = {}
        for item in await self.repository.list_messages(wa_id):
            if item["direction"] == "inbound":
                slots.update(self._extract_appointment_slots(str(item["text"])))
        return slots

    async def _has_pending_appointment_prompt(self, wa_id: str) -> bool:
        for item in reversed(await self.repository.list_messages(wa_id)):
            if item["direction"] != "outbound":
                continue
            text = str(item["text"])
            return text.startswith(APPOINTMENT_PROMPT_PREFIX) or text.startswith("Ya registre ")
        return False

    @staticmethod
    def _appointment_recorded_text(slots: dict[str, str]) -> str:
        labels = {
            "tipo_cita": "tipo de cita",
            "especialidad": "especialidad",
            "eps": "EPS",
            "urgencia": "prioridad",
        }
        return ", ".join(f"{labels[key]} {slots[key]}" for key in APPOINTMENT_SLOTS if key in slots)

    @staticmethod
    def _appointment_selection(text: str) -> int | None:
        normalized = text.lower().strip()
        match = re.search(r"(?:opcion\s*)?([123])\b", normalized)
        return int(match.group(1)) if match else None

    @staticmethod
    def _appointment_availability_response(slots: dict[str, str]) -> str:
        options = "\n".join(
            f"{index}. {slot}"
            for index, slot in enumerate(ConversationService._appointment_availability(), start=1)
        )
        return (
            "Tengo estas disponibilidades simuladas para tu cita "
            f"{slots['tipo_cita'].lower()} de {slots['especialidad']} con EPS {slots['eps']}:\n"
            f"{options}\nResponde Opcion 1, Opcion 2 u Opcion 3 para confirmar."
        )

    @staticmethod
    def _appointment_availability() -> list[str]:
        weekday_names = {
            0: "lunes",
            1: "martes",
            2: "miercoles",
            3: "jueves",
            4: "viernes",
        }
        month_names = {
            1: "enero",
            2: "febrero",
            3: "marzo",
            4: "abril",
            5: "mayo",
            6: "junio",
            7: "julio",
            8: "agosto",
            9: "septiembre",
            10: "octubre",
            11: "noviembre",
            12: "diciembre",
        }
        hours = ("9:00 a.m.", "11:30 a.m.", "3:00 p.m.")
        current = date.today()
        cursor = current + timedelta(days=1)
        remaining_weekdays: list[date] = []
        while cursor.weekday() >= current.weekday() and cursor.weekday() < 5:
            remaining_weekdays.append(cursor)
            cursor += timedelta(days=1)
        if not remaining_weekdays:
            while len(remaining_weekdays) < 2:
                if cursor.weekday() < 5:
                    remaining_weekdays.append(cursor)
                cursor += timedelta(days=1)
        weekdays = [
            remaining_weekdays[0],
            remaining_weekdays[min(1, len(remaining_weekdays) - 1)],
            remaining_weekdays[min(1, len(remaining_weekdays) - 1)],
        ]
        return [
            f"{weekday_names[day.weekday()]} {day.day} de {month_names[day.month]} "
            f"de {day.year}, {hour}"
            for day, hour in zip(weekdays, hours, strict=True)
        ]

    @staticmethod
    def _administrative_response(text: str) -> str:
        normalized = "".join(
            character
            for character in unicodedata.normalize("NFD", text.lower())
            if unicodedata.category(character) != "Mn"
        )
        if "horario" in normalized or "sabado" in normalized:
            return (
                "Nuestros horarios de atencion son: lunes a viernes de 7:00 a.m. a "
                "7:00 p.m. y sabados de 8:00 a.m. a 1:00 p.m. "
                "La atencion de urgencias opera 24/7."
            )
        if "ubic" in normalized or "donde" in normalized or "sede" in normalized:
            return (
                "Para esta demostracion, la sede principal esta en Bogota. "
                "Al llegar, recepcion puede orientarte al servicio de psiquiatria."
            )
        if "sanitas" in normalized:
            return (
                "Para la demostracion registramos convenio con EPS Sanitas. "
                "La autorizacion y cobertura se validan antes de confirmar atencion."
            )
        if "cuanto cuesta" in normalized or "particular" in normalized:
            return (
                "El valor de una consulta particular debe confirmarse segun especialidad "
                "y modalidad. Puedo ayudarte a registrar una solicitud de cita."
            )
        if "autorizacion" in normalized:
            return (
                "Solicita la autorizacion directamente a tu EPS indicando la especialidad "
                "requerida. Cuando tengas el soporte, podemos registrar tu cita."
            )
        if "certificado" in normalized:
            return (
                "Los certificados de incapacidad son gestionados por el equipo autorizado "
                "despues de validar la atencion correspondiente."
            )
        return "Puedo orientarte sobre horarios, sede, convenios, autorizaciones o tramites."

    @staticmethod
    def _extract_appointment_slots(text: str) -> dict[str, str]:
        normalized = "".join(
            character
            for character in unicodedata.normalize("NFD", text.lower())
            if unicodedata.category(character) != "Mn"
        )
        slots: dict[str, str] = {}
        specialties = {
            "psiquiatr": "Psiquiatria",
            "psicolog": "Psicologia",
            "neuropsicolog": "Neuropsicologia",
        }
        eps_names = {
            "compensar": "Compensar",
            "sanitas": "Sanitas",
            "nueva eps": "Nueva EPS",
            "sura": "Sura",
            "salud total": "Salud Total",
            "famisanar": "Famisanar",
        }
        for token, value in specialties.items():
            if token in normalized:
                slots["especialidad"] = value
                break
        for token, value in eps_names.items():
            if token in normalized:
                slots["eps"] = value
                break
        if any(term in normalized for term in ("no es de control", "no es control", "primera vez")):
            slots["tipo_cita"] = "Primera vez"
        elif "control" in normalized:
            slots["tipo_cita"] = "Control"
        elif "reprogram" in normalized:
            slots["tipo_cita"] = "Reprogramacion"
        if any(term in normalized for term in ("no urgente", "sin urgencia", "no es urgente")):
            slots["urgencia"] = "No urgente"
        elif "urgente" in normalized or "prioritari" in normalized or "cita ya" in normalized:
            slots["urgencia"] = "Urgente"
        return slots

    async def _respond(self, wa_id: str, text: str) -> None:
        local_id = await self.repository.queue_outbound(wa_id, text)
        try:
            meta_id = await self.messenger.send(OutboundMessage(wa_id=wa_id, text=text))
            await self.repository.mark_outbound_sent(local_id, meta_id)
        except Exception as exc:
            await self.repository.mark_outbound_failed(local_id, str(exc))
            raise
