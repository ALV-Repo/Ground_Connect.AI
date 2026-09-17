import pytest

from gateway.gateway import AIGateway
from gateway.pii_masker import PIIMasker


def test_email_is_masked():
    masker = PIIMasker()

    text = "Contact citizen@example.com"

    result = masker.mask(text)

    assert "citizen@example.com" not in result
    assert "[EMAIL_REDACTED]" in result


def test_phone_is_masked():
    masker = PIIMasker()

    text = "Citizen phone: 9876543210"

    result = masker.mask(text)

    assert "9876543210" not in result
    assert "[PHONE_REDACTED]" in result


def test_aadhaar_is_masked():
    masker = PIIMasker()

    text = "Aadhaar: 1234 5678 9012"

    result = masker.mask(text)

    assert "1234 5678 9012" not in result
    assert "[AADHAAR_REDACTED]" in result


@pytest.mark.asyncio
async def test_approved_provider_works():
    gateway = AIGateway()

    response = await gateway.generate(
        prompt="Hello GroundConnect",
        provider="mock",
    )

    assert response.provider == "mock"
    assert response.model == "mock-model"


@pytest.mark.asyncio
async def test_unapproved_provider_is_rejected():
    gateway = AIGateway()

    with pytest.raises(ValueError):
        await gateway.generate(
            prompt="Hello",
            provider="fake-provider",
        )


@pytest.mark.asyncio
async def test_gateway_detects_pii():
    gateway = AIGateway()

    response = await gateway.generate(
        prompt="Email citizen@example.com",
        provider="mock",
    )

    assert response.pii_masked is True