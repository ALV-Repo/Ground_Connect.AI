from pydantic import BaseModel, Field


class AIRequest(BaseModel):

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=10000,
    )

    provider: str | None = None
    model: str | None = None


class AIResponseModel(BaseModel):

    provider: str
    model: str
    content: str
    pii_masked: bool