# providers/base_provider.py
from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    def stream_response(self, message: str, context: list, model: str):
        raise NotImplementedError
