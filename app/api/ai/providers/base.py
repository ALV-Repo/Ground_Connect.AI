from abc import ABC, abstractmethod


class AIProvider(ABC):

    @abstractmethod
    def summarize(
        self,
        text: str,
        content_type: str = "general",
    ) -> str:
        pass

    @abstractmethod
    def translate(
        self,
        text: str,
        target_language: str,
    ) -> str:
        pass

    @abstractmethod
    def transcribe(
        self,
        filename: str,
        language: str | None = None,
    ) -> dict:
        pass