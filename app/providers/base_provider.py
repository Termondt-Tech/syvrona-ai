# providers/base_provider.py
class AIProvider:
    def stream_response(self, message: str, context: list, model: str):
        raise NotImplementedError
