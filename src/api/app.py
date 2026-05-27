"""HTTP adapter exposing WhatsApp webhook and local development endpoints."""

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import (
    BackgroundTasks,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from src.adapters.sqlite import SQLiteConversationRepository
from src.adapters.whatsapp.client import ConsoleMessenger, MetaWhatsAppMessenger
from src.adapters.whatsapp.webhook import parse_inbound_messages, parse_statuses, verify_signature
from src.application import ConversationService
from src.domain.models import InboundMessage
from src.settings import AppSettings


class SimulateRequest(BaseModel):
    wa_id: str = "573000000000"
    name: str | None = "Usuario Demo"
    text: str


def create_app(settings: AppSettings | None = None) -> FastAPI:
    config = settings or AppSettings()
    repository = SQLiteConversationRepository(config.db_path, config.field_encryption_key)
    messenger = (
        MetaWhatsAppMessenger(config) if config.whatsapp_send_mode == "meta" else ConsoleMessenger()
    )
    service = ConversationService(repository, messenger)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await repository.initialize()
        yield

    app = FastAPI(title="Clinica Retornar - Agente Local", lifespan=lifespan)
    app.state.repository = repository
    app.state.service = service
    app.state.settings = config

    async def process_simulation(body: SimulateRequest):
        if config.app_env != "local":
            raise HTTPException(status_code=404, detail="No disponible")
        return await service.process(
            InboundMessage(
                wa_id=body.wa_id,
                user_name=body.name,
                text=body.text,
                message_id=f"dev.{uuid4()}",
            )
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "send_mode": config.whatsapp_send_mode}

    @app.get("/webhook")
    async def verify_webhook(
        hub_mode: str = Query(alias="hub.mode"),
        hub_verify_token: str = Query(alias="hub.verify_token"),
        hub_challenge: str = Query(alias="hub.challenge"),
    ) -> PlainTextResponse:
        if hub_mode != "subscribe" or hub_verify_token != config.whatsapp_verify_token:
            raise HTTPException(status_code=403, detail="Token de verificacion invalido")
        return PlainTextResponse(hub_challenge)

    @app.post("/webhook")
    async def receive_webhook(
        request: Request,
        background_tasks: BackgroundTasks,
        x_hub_signature_256: str | None = Header(default=None),
    ) -> dict[str, str]:
        raw = await request.body()
        if not verify_signature(raw, x_hub_signature_256, config.whatsapp_app_secret):
            raise HTTPException(status_code=401, detail="Firma invalida")
        payload = await request.json()
        for meta_id, status in parse_statuses(payload):
            await repository.update_delivery_status(meta_id, status)
        for inbound in parse_inbound_messages(payload):
            background_tasks.add_task(service.process, inbound)
        return {"status": "accepted"}

    @app.post("/dev/simulate")
    async def simulate(body: SimulateRequest) -> dict[str, object]:
        outcome = await process_simulation(body)
        return {
            "status": outcome.status,
            "responses": outcome.responses,
            "classification": (
                outcome.classification.model_dump(mode="json") if outcome.classification else None
            ),
        }

    @app.post("/dev/simulate/pretty", response_class=PlainTextResponse)
    async def simulate_pretty(body: SimulateRequest) -> PlainTextResponse:
        outcome = await process_simulation(body)
        result = outcome.classification
        responses = outcome.responses or ["(sin respuesta automatica)"]
        lines = [
            "CLINICA RETORNAR - DEMO LOCAL",
            "=" * 64,
            f"Usuario: {body.text or '<mensaje vacio>'}",
            "",
            "Respuesta del agente:",
            *[f"  {response}" for response in responses],
            "",
            "Resultado tecnico:",
            f"  Estado: {outcome.status}",
        ]
        if result:
            lines.extend(
                [
                    f"  Categoria: {result.category.value}",
                    f"  Accion: {result.suggested_action.value}",
                    f"  Confianza: {result.confidence:.2f}",
                    f"  Riesgo: {result.metadata.risk_level.value}",
                    f"  Modelo/regla: {result.metadata.model_used or 'no aplica'}",
                ]
            )
        lines.append("=" * 64)
        return PlainTextResponse("\n".join(lines))

    @app.websocket("/ws/whatsapp")
    async def whatsapp_bridge(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                body = await websocket.receive_json()
                text = str(body.get("text", "")).strip()
                wa_id = str(body.get("from", "")).strip()
                if not text or not wa_id:
                    continue
                outcome = await service.process(
                    InboundMessage(
                        wa_id=wa_id,
                        user_name=str(body.get("push_name", "")).strip() or None,
                        text=text,
                        message_id=str(body.get("message_id", "")).strip() or f"baileys.{uuid4()}",
                    )
                )
                for response in outcome.responses:
                    await websocket.send_json({"to": wa_id, "text": response})
        except WebSocketDisconnect:
            return

    @app.get("/dev/messages/{wa_id}")
    async def messages(wa_id: str) -> list[dict[str, object]]:
        if config.app_env != "local":
            raise HTTPException(status_code=404, detail="No disponible")
        return await repository.list_messages(wa_id)

    @app.get("/dev/escalations")
    async def escalations() -> list[dict[str, object]]:
        if config.app_env != "local":
            raise HTTPException(status_code=404, detail="No disponible")
        return await repository.list_escalations()

    return app
