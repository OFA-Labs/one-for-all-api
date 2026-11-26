import io

from fastapi.testclient import TestClient

from voice.api import create_app
from voice.config import Settings
from voice.events import Events


def test_health_reports_speech_configuration_without_secrets():
    settings = Settings()
    app = create_app(settings, Events("fake", io.StringIO()), None, "x" * 48)
    with TestClient(app, base_url="http://127.0.0.1:8767") as client:
        body = client.get("/v1/health").json()

    assert body["version"] == "0.2.3"
    assert body["identity_mode"] == "local-development"
    speech = body["speech"]
    assert speech["mode"] == "fake"
    assert speech["language"] == "auto"
    assert speech["stt_order"] == ["deepgram", "gradium"]
    assert speech["tts_order"] == ["deepgram", "gradium"]
    assert speech["deepgram_configured"] is False
    assert speech["gradium_configured"] is False
    assert speech["engine_enabled"] is False
    assert "key" not in str(body).lower()
