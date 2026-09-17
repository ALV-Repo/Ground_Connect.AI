from gateway.gateway import AIGateway
from models.ai import AIRequest, AIResponseModel


class AIService:

    def __init__(self):
        self.gateway = AIGateway()

    async def generate(
        self,
        request: AIRequest,
    ) -> AIResponseModel:

        response = await self.gateway.generate(
            prompt=request.prompt,
            provider=request.provider,
            model=request.model,
        )

        return AIResponseModel(
            provider=response.provider,
            model=response.model,
            content=response.content,
            pii_masked=response.pii_masked,
        )