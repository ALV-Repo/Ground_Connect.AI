from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


# =========================================================
# AI-011 SUMMARISATION
# =========================================================


def test_summarize():
    response = client.post(
        "/api/v1/ai/summarize",
        json={
            "text": (
                "The field team visited Ward 12 and inspected "
                "15 streetlights. Three streetlights were not "
                "working and the issue was reported to the "
                "maintenance team."
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "summary" in data
    assert data["summary"]
    assert data["content_type"] == "general"


def test_summarize_message_thread():
    response = client.post(
        "/api/v1/ai/summarize",
        json={
            "text": (
                "Citizen reported a broken streetlight. "
                "The field team inspected the location "
                "and assigned the issue to maintenance."
            ),
            "content_type": "message_thread",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["content_type"] == "message_thread"
    assert data["summary"]


def test_summarize_field_report():
    response = client.post(
        "/api/v1/ai/summarize",
        json={
            "text": (
                "Ward 5 field report contains multiple "
                "road maintenance observations."
            ),
            "content_type": "field_report",
        },
    )

    assert response.status_code == 200

    assert response.json()["content_type"] == "field_report"


def test_summarize_meeting():
    response = client.post(
        "/api/v1/ai/summarize",
        json={
            "text": (
                "The meeting discussed water supply, "
                "road repairs and sanitation activities."
            ),
            "content_type": "meeting",
        },
    )

    assert response.status_code == 200

    assert response.json()["content_type"] == "meeting"


def test_batch_summarization():
    response = client.post(
        "/api/v1/ai/summarize/batch",
        json={
            "texts": [
                "First field report.",
                "Second field report.",
                "Third field report.",
            ],
            "content_type": "field_report",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["content_type"] == "field_report"
    assert len(data["summaries"]) == 3


def test_invalid_summary_content_type():
    response = client.post(
        "/api/v1/ai/summarize",
        json={
            "text": "Test content.",
            "content_type": "invalid_type",
        },
    )

    assert response.status_code == 422


def test_summarize_empty_text():
    response = client.post(
        "/api/v1/ai/summarize",
        json={
            "text": "",
        },
    )

    assert response.status_code == 422


# =========================================================
# AI-012 TRANSLATION
# =========================================================


def test_translate_hindi():
    response = client.post(
        "/api/v1/ai/translate",
        json={
            "text": "good morning",
            "target_language": "hindi",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["original_text"] == "good morning"
    assert data["target_language"] == "hindi"
    assert data["translated_text"] == "सुप्रभात"
    assert data["quality_label"] == "machine-translated"


def test_translate_kannada():
    response = client.post(
        "/api/v1/ai/translate",
        json={
            "text": "good morning",
            "target_language": "kannada",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["translated_text"] == "ಶುಭೋದಯ"


def test_translate_english():
    response = client.post(
        "/api/v1/ai/translate",
        json={
            "text": "नमस्ते",
            "target_language": "english",
        },
    )

    assert response.status_code == 200

    assert response.json()["translated_text"] == "Hello"


def test_translate_using_language_code():
    response = client.post(
        "/api/v1/ai/translate",
        json={
            "text": "good morning",
            "target_language": "hi",
        },
    )

    assert response.status_code == 200
    assert response.json()["translated_text"] == "सुप्रभात"


def test_translate_empty_text():
    response = client.post(
        "/api/v1/ai/translate",
        json={
            "text": "",
            "target_language": "hindi",
        },
    )

    assert response.status_code == 422


def test_translate_unsupported_language():
    response = client.post(
        "/api/v1/ai/translate",
        json={
            "text": "hello",
            "target_language": "tamil",
        },
    )

    assert response.status_code == 422


# =========================================================
# AI-013 TRANSCRIPTION
# =========================================================


def test_transcribe():
    response = client.post(
        "/api/v1/ai/transcribe?language=en-IN",
        files={
            "file": (
                "test.wav",
                b"dummy audio data",
                "audio/wav",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "transcript" in data
    assert data["language"] == "en-IN"
    assert 0 <= data["confidence"] <= 1
    assert data["speaker_confirmed"] is False
    assert data["committed"] is False
    assert data["requires_confirmation"] is True


def test_transcribe_hindi():
    response = client.post(
        "/api/v1/ai/transcribe?language=hi-IN",
        files={
            "file": (
                "test.wav",
                b"dummy audio data",
                "audio/wav",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["language"] == "hi-IN"


def test_transcribe_kannada():
    response = client.post(
        "/api/v1/ai/transcribe?language=kn-IN",
        files={
            "file": (
                "test.wav",
                b"dummy audio data",
                "audio/wav",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["language"] == "kn-IN"


def test_transcribe_default_language():
    response = client.post(
        "/api/v1/ai/transcribe",
        files={
            "file": (
                "test.wav",
                b"dummy audio data",
                "audio/wav",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["language"] == "hi-IN"


def test_transcribe_unsupported_language():
    response = client.post(
        "/api/v1/ai/transcribe?language=fr-FR",
        files={
            "file": (
                "test.wav",
                b"dummy audio data",
                "audio/wav",
            )
        },
    )

    assert response.status_code == 422


def test_transcribe_rejects_unsupported_file_type():
    response = client.post(
        "/api/v1/ai/transcribe?language=en-IN",
        files={
            "file": (
                "test.txt",
                b"this is not audio",
                "text/plain",
            )
        },
    )

    assert response.status_code == 415


def test_transcribe_rejects_empty_audio():
    response = client.post(
        "/api/v1/ai/transcribe?language=en-IN",
        files={
            "file": (
                "empty.wav",
                b"",
                "audio/wav",
            )
        },
    )

    assert response.status_code == 400


def test_transcribe_requires_audio_file():
    response = client.post(
        "/api/v1/ai/transcribe?language=en-IN"
    )

    assert response.status_code == 422


def test_transcribe_rejects_oversized_audio():
    oversized_audio = (
        b"x" * (10 * 1024 * 1024 + 1)
    )

    response = client.post(
        "/api/v1/ai/transcribe?language=en-IN",
        files={
            "file": (
                "large.wav",
                oversized_audio,
                "audio/wav",
            )
        },
    )

    assert response.status_code == 413


def test_transcribe_accepts_supported_audio_types():
    supported_types = [
        ("audio.wav", "audio/wav"),
        ("audio.mp3", "audio/mpeg"),
        ("audio.mp4", "audio/mp4"),
        ("audio.ogg", "audio/ogg"),
        ("audio.webm", "audio/webm"),
    ]

    for filename, content_type in supported_types:
        response = client.post(
            "/api/v1/ai/transcribe?language=en-IN",
            files={
                "file": (
                    filename,
                    b"dummy audio data",
                    content_type,
                )
            },
        )

        assert response.status_code == 200


# =========================================================
# SPEAKER CONFIRMATION
# =========================================================


def test_transcription_requires_confirmation():
    response = client.post(
        "/api/v1/ai/transcribe/confirm",
        json={
            "transcript": "Test transcript",
            "language": "en-IN",
            "confidence": 0.92,
            "speaker_confirmed": False,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["speaker_confirmed"] is False
    assert data["committed"] is False
    assert data["requires_confirmation"] is True


def test_transcription_commit_after_confirmation():
    response = client.post(
        "/api/v1/ai/transcribe/confirm",
        json={
            "transcript": "Test transcript",
            "language": "en-IN",
            "confidence": 0.92,
            "speaker_confirmed": True,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["speaker_confirmed"] is True
    assert data["committed"] is True
    assert data["requires_confirmation"] is False


def test_low_confidence_cannot_commit():
    response = client.post(
        "/api/v1/ai/transcribe/confirm",
        json={
            "transcript": "Low confidence transcript",
            "language": "en-IN",
            "confidence": 0.50,
            "speaker_confirmed": True,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["committed"] is False
    assert data["requires_confirmation"] is True
    assert data["quality_label"] == "low-confidence"


def test_invalid_confidence():
    response = client.post(
        "/api/v1/ai/transcribe/confirm",
        json={
            "transcript": "Test transcript",
            "language": "en-IN",
            "confidence": 1.5,
            "speaker_confirmed": True,
        },
    )

    assert response.status_code == 422


def test_negative_confidence():
    response = client.post(
        "/api/v1/ai/transcribe/confirm",
        json={
            "transcript": "Test transcript",
            "language": "en-IN",
            "confidence": -0.1,
            "speaker_confirmed": True,
        },
    )

    assert response.status_code == 422


def test_confirmation_does_not_commit_when_false():
    response = client.post(
        "/api/v1/ai/transcribe/confirm",
        json={
            "transcript": "Test transcript",
            "language": "hi-IN",
            "confidence": 0.85,
            "speaker_confirmed": False,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["committed"] is False
    assert data["speaker_confirmed"] is False


def test_confirmation_preserves_transcription_data():
    response = client.post(
        "/api/v1/ai/transcribe/confirm",
        json={
            "transcript": "Hello Ground Connect",
            "language": "en-IN",
            "confidence": 0.95,
            "speaker_confirmed": True,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["transcript"] == "Hello Ground Connect"
    assert data["language"] == "en-IN"
    assert data["confidence"] == 0.95
    assert data["speaker_confirmed"] is True
    assert data["committed"] is True


# =========================================================
# TTS / READ BACK
# =========================================================


def test_transcription_read_back():
    response = client.post(
        "/api/v1/ai/transcribe/read-back",
        json={
            "text": "Hello Ground Connect",
            "language": "en-IN",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["text"] == "Hello Ground Connect"
    assert data["language"] == "en-IN"
    assert data["provider"] == "mock"
    assert data["audio_available"] is False


def test_read_back_hindi():
    response = client.post(
        "/api/v1/ai/transcribe/read-back",
        json={
            "text": "नमस्ते",
            "language": "hi-IN",
        },
    )

    assert response.status_code == 200
    assert response.json()["language"] == "hi-IN"


def test_read_back_unsupported_language():
    response = client.post(
        "/api/v1/ai/transcribe/read-back",
        json={
            "text": "Hello",
            "language": "fr-FR",
        },
    )

    assert response.status_code == 422


# =========================================================
# AI GATEWAY
# =========================================================


def test_ai_gateway_summarize():
    from app.api.ai.gateway import ai_gateway

    result = ai_gateway.summarize(
        "This is a test sentence for summarization."
    )

    assert isinstance(result, str)
    assert result


def test_ai_gateway_translate():
    from app.api.ai.gateway import ai_gateway

    result = ai_gateway.translate(
        "good morning",
        "hindi",
    )

    assert result == "सुप्रभात"


def test_ai_gateway_transcribe():
    from app.api.ai.gateway import ai_gateway

    result = ai_gateway.transcribe(
        "test.wav",
        "en-IN",
    )

    assert isinstance(result, dict)
    assert result["language"] == "en-IN"
    assert result["confidence"] == 0.92