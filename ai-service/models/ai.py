from pydantic import BaseModel, Field


class AIRequest(BaseModel):

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=10000,
    )

    conversation_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    provider: str | None = None
    model: str | None = None

    user_id: str = Field(
        ...,
        min_length=1,
    )

    user_role: str = Field(
        ...,
        min_length=1,
    )

    organization_id: str = Field(
        ...,
        min_length=1,
    )

    resource_organization_id: str = Field(
        ...,
        min_length=1,
    )


class AIResponseModel(BaseModel):

    provider: str
    model: str
    content: str
    pii_masked: bool
    prompt_injection_detected: bool


class CopilotRequest(BaseModel):

    question: str = Field(
        ...,
        min_length=1,
        max_length=10000,
    )

    conversation_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    user_id: str = Field(
        ...,
        min_length=1,
    )

    user_role: str = Field(
        ...,
        min_length=1,
    )

    organization_id: str = Field(
        ...,
        min_length=1,
    )

    resource_organization_id: str = Field(
        ...,
        min_length=1,
    )

    provider: str | None = None

    model: str | None = None


class CopilotResponse(BaseModel):

    answer: str

    provider: str

    model: str

    pii_masked: bool

    prompt_injection_detected: bool

    # AI-007:
    # Coverage and freshness disclosure.
    coverage: str

    freshness: str

    # AI-008:
    # Explicit separation of facts, inferences,
    # and recommendations.
    facts: list[str]

    inferences: list[str]

    recommendations: list[str]