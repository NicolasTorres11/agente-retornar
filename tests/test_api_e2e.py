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
            "/dev/simulate", json={"wa_id": "571", "text": "Necesito cita con psiquiatria"}
        )
        assert processed.json()["status"] == "processed"
        assert processed.json()["classification"]["category"] == "solicitud_cita"

        messages = client.get("/dev/messages/571").json()
        assert len(messages) == 6
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
