import asyncio
import hashlib
import hmac
import json

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from src.api import create_app
from src.settings import AppSettings


def _app(tmp_path, monkeypatch):
    monkeypatch.setenv("CLASSIFIER_OFFLINE_MODE", "true")
    settings = AppSettings(
        db_path=tmp_path / "demo.db",
        field_encryption_key=Fernet.generate_key().decode("ascii"),
        whatsapp_app_secret="test-secret",
        whatsapp_verify_token="test-token",
        whatsapp_send_mode="console",
    )
    return create_app(settings)


def test_local_flow_consent_then_appointment(tmp_path, monkeypatch) -> None:
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        first = client.post("/dev/simulate", json={"wa_id": "571", "text": "Quiero una cita"})
        assert first.json()["status"] == "consent_requested"

        consent = client.post("/dev/simulate", json={"wa_id": "571", "text": "SI AUTORIZO"})
        assert consent.json()["status"] == "consent_accepted"

        processed = client.post(
            "/dev/simulate", json={"wa_id": "571", "text": "Quisiera agendar una cita"}
        )
        assert processed.json()["status"] == "processed"
        assert processed.json()["classification"]["category"] == "solicitud_cita"
        assert "especialidad" in processed.json()["responses"][0]

        details = client.post(
            "/dev/simulate",
            json={"wa_id": "571", "text": "Psiquiatria. Compensar y no es de control."},
        )
        assert "urgente" in details.json()["responses"][0]
        assert "EPS Compensar" in details.json()["responses"][0]

        completed = client.post("/dev/simulate", json={"wa_id": "571", "text": "No urgente"})
        assert "disponibilidades simuladas" in completed.json()["responses"][0]
        assert "Psiquiatria" in completed.json()["responses"][0]
        assert "Compensar" in completed.json()["responses"][0]

        selected = client.post("/dev/simulate", json={"wa_id": "571", "text": "Opcion 1"})
        assert "Cita de demostracion confirmada" in selected.json()["responses"][0]
        assert "simulado para la prueba local" in selected.json()["responses"][0]

        messages = client.get("/dev/messages/571").json()
        assert len(messages) == 12
        assert messages[-1]["direction"] == "outbound"


def test_crisis_is_escalated_before_consent(tmp_path, monkeypatch) -> None:
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        response = client.post(
            "/dev/simulate", json={"wa_id": "572", "text": "Me quiero matar, tengo las pastillas"}
        )
        assert response.json()["status"] == "crisis_escalated"
        assert response.json()["classification"]["suggested_action"] == "escalar_crisis_emocional"
        escalations = client.get("/dev/escalations").json()
        assert escalations[0]["priority"] == "critical"


def test_authorized_admin_question_gets_direct_answer(tmp_path, monkeypatch) -> None:
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        client.post("/dev/simulate", json={"wa_id": "admin", "text": "Hola"})
        client.post("/dev/simulate", json={"wa_id": "admin", "text": "SI AUTORIZO"})
        response = client.post(
            "/dev/simulate",
            json={"wa_id": "admin", "text": "Cuales son los horarios de atencion los sabados?"},
        )
        assert "sabados de 8:00 a.m. a 1:00 p.m." in response.json()["responses"][0]


def test_video_appointment_case_offers_simulated_availability(tmp_path, monkeypatch) -> None:
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        client.post("/dev/simulate", json={"wa_id": "video", "text": "Hola"})
        client.post("/dev/simulate", json={"wa_id": "video", "text": "SI AUTORIZO"})
        request = client.post(
            "/dev/simulate",
            json={
                "wa_id": "video",
                "text": (
                    "Hola, necesito agendar cita de control con psiquiatria, atiendo por Sanitas"
                ),
            },
        )
        assert "urgente" in request.json()["responses"][0]
        available = client.post("/dev/simulate", json={"wa_id": "video", "text": "No urgente"})
        assert "disponibilidades simuladas" in available.json()["responses"][0]
        assert "EPS Sanitas" in available.json()["responses"][0]


def test_new_appointment_does_not_reuse_previous_urgent_slots(tmp_path, monkeypatch) -> None:
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        client.post("/dev/simulate", json={"wa_id": "repeat", "text": "Hola"})
        client.post("/dev/simulate", json={"wa_id": "repeat", "text": "SI AUTORIZO"})
        client.post("/dev/simulate", json={"wa_id": "repeat", "text": "Quiero una cita"})
        urgent = client.post(
            "/dev/simulate",
            json={"wa_id": "repeat", "text": "Primera vez, psiquiatria, Sanitas, urgente"},
        )
        assert "solicitud como urgente" in urgent.json()["responses"][0]

        new_request = client.post(
            "/dev/simulate", json={"wa_id": "repeat", "text": "Quiero una cita"}
        )
        assert "Con gusto te ayudo a gestionar tu cita" in new_request.json()["responses"][0]
        assert "solicitud como urgente" not in new_request.json()["responses"][0]

        available = client.post(
            "/dev/simulate",
            json={"wa_id": "repeat", "text": "Control, psiquiatria, Sanitas, no urgente"},
        )
        assert "disponibilidades simuladas" in available.json()["responses"][0]


def test_previous_registered_appointment_is_upgraded_to_schedule_selection(
    tmp_path, monkeypatch
) -> None:
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        client.post("/dev/simulate", json={"wa_id": "legacy", "text": "Hola"})
        client.post("/dev/simulate", json={"wa_id": "legacy", "text": "SI AUTORIZO"})
        asyncio.run(
            client.app.state.repository.save_appointment(
                "legacy",
                {
                    "tipo_cita": "Control",
                    "especialidad": "Psiquiatria",
                    "eps": "Sanitas",
                    "urgencia": "No urgente",
                },
                status="requested",
            )
        )
        response = client.post("/dev/simulate", json={"wa_id": "legacy", "text": "Continuar"})
        assert "disponibilidades simuladas" in response.json()["responses"][0]


def test_clinical_and_pqr_responses_explain_handoff(tmp_path, monkeypatch) -> None:
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        for wa_id in ("clinical", "pqr"):
            client.post("/dev/simulate", json={"wa_id": wa_id, "text": "Hola"})
            client.post("/dev/simulate", json={"wa_id": wa_id, "text": "SI AUTORIZO"})
        clinical = client.post(
            "/dev/simulate",
            json={"wa_id": "clinical", "text": "Olvide tomar la sertralina anoche, que hago?"},
        )
        assert "No puedo recomendar cambios de medicacion" in clinical.json()["responses"][0]
        pqr = client.post(
            "/dev/simulate",
            json={"wa_id": "pqr", "text": "Me cobraron mal la consulta, exijo devolucion"},
        )
        assert "15 dias habiles" in pqr.json()["responses"][0]


def test_whatsapp_verification_handshake(tmp_path, monkeypatch) -> None:
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        response = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test-token",
                "hub.challenge": "123456",
            },
        )
        assert response.status_code == 200
        assert response.text == "123456"


def test_whatsapp_signed_inbound_payload_is_processed(tmp_path, monkeypatch) -> None:
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [{"profile": {"name": "Maria"}}],
                                "messages": [
                                    {
                                        "from": "57300999",
                                        "id": "wamid.demo.1",
                                        "timestamp": "1730000000",
                                        "type": "text",
                                        "text": {"body": "Hola"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        body = json.dumps(payload).encode("utf-8")
        signature = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
        response = client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={signature}",
            },
        )
        assert response.status_code == 200
        messages = client.get("/dev/messages/57300999").json()
        assert messages[0]["text"] == "Hola"
        assert messages[1]["direction"] == "outbound"


def test_whatsapp_invalid_signature_is_rejected(tmp_path, monkeypatch) -> None:
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        response = client.post(
            "/webhook",
            json={"entry": []},
            headers={"X-Hub-Signature-256": "sha256=incorrecta"},
        )
        assert response.status_code == 401


def test_baileys_websocket_bridge_processes_message(tmp_path, monkeypatch) -> None:
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        with client.websocket_connect("/ws/whatsapp") as websocket:
            websocket.send_json(
                {
                    "from": "57300123@s.whatsapp.net",
                    "message_id": "baileys.1",
                    "text": "Quiero una cita",
                    "push_name": "Demo",
                }
            )
            response = websocket.receive_json()
            assert response["to"] == "57300123@s.whatsapp.net"
            assert "autorizacion" in response["text"]
