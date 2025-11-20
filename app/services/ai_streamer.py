from datetime import UTC, datetime
import io
import logging
import time
from typing import Any, Dict, Generator, Optional

from sqlalchemy.dialects.mysql import insert
from sqlalchemy import literal_column

from app.model_registry import get_model_metadata
from app.providers.gemini_provider import GeminiProvider
from app.providers.openai_provider import OpenAIProvider, ModelAccessError
from app.providers.anthropic_provider import AnthropicProvider
from app.models import UsageStat, create_message, db
from app.tokenizer import get_tokenizer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------- #
#  Helpers                                                               #
# ---------------------------------------------------------------------- #
class MessagePersister:
    def save_user(self, conv_id: Optional[int], body: str, model: str) -> Any:
        msg = create_message(conv_id, "user", body, model)
        logger.info(
            "User message saved: id=%s conv=%s model=%s", msg.id, conv_id, model
        )
        return msg

    def save_assistant(self, conv_id: Optional[int], body: str, model: str) -> Any:
        msg = create_message(conv_id, "assistant", body, model)
        logger.info(
            "Assistant message saved: id=%s conv=%s model=%s", msg.id, conv_id, model
        )
        return msg


class ProviderRegistry:
    """Resolves provider instances by provider key."""

    def __init__(self, providers: Optional[Dict[str, Any]] = None) -> None:
        self._providers = providers or {
            "openai": OpenAIProvider(),
            "anthropic": AnthropicProvider(),
            "gemini": GeminiProvider(),
        }

    def get_provider(self, key: str) -> Any:
        try:
            return self._providers[key]
        except KeyError as exc:
            raise ValueError(f"No provider registered for key '{key}'") from exc


# ---------------------------------------------------------------------- #
#  Main streamer                                                         #
# ---------------------------------------------------------------------- #
class AIStreamer:
    """Facade for provider selection, token streaming, persistence, and quota."""

    def __init__(
        self,
        provider_registry: Optional[ProviderRegistry] = None,
        persister: Optional[MessagePersister] = None,
        logger_: Optional[logging.Logger] = None,
    ) -> None:
        self._providers = provider_registry or ProviderRegistry()
        self._persist = persister or MessagePersister()
        self._log = logger_ or logger

    # ------------------------------------------------------------------ #
    #  Atomic monthly token counter                                      #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _inc_usage(user_id: int, inc_tokens: int) -> None:
        """Add `inc_tokens` to the user’s monthly total (MySQL 8.0 upsert)."""
        if inc_tokens <= 0:
            return

        period_start = datetime.now(tz=UTC).date().replace(day=1)

        stmt = (
            insert(UsageStat)
            .values(
                user_id=user_id,
                period_start=period_start,
                tokens=inc_tokens,  # initial value if row is new
            )
            .on_duplicate_key_update(  # runs when UNIQUE hits
                tokens=UsageStat.tokens + literal_column(str(inc_tokens))
            )
        )
        db.session.execute(stmt)
        db.session.commit()

    # ---------- Public entry-point ------------------------------------- #
    def chat(
        self,
        user_prompt: str,
        user_id: int,
        conversation_id: Optional[int],
        model_name: str,
        _visited: Optional[set[str]] = None,
    ) -> Generator[str, None, None]:

        _visited = _visited or set()
        if model_name in _visited:
            raise RuntimeError(
                f"Fallback recursion detected; already tried {model_name}"
            )
        _visited.add(model_name)

        start = time.monotonic()
        meta = get_model_metadata(model_name)
        provider_key = meta.get("provider") or ""
        provider = self._providers.get_provider(provider_key)

        system_prompt = meta.get("system_prompt", "You are an intelligent assistant.")
        fallback_model = meta.get("fallback_model")

        # 1) persist user message
        self._persist.save_user(conversation_id, user_prompt, model_name)

        tokenizer = get_tokenizer(model_name)
        prompt_tokens = len(tokenizer.encode(user_prompt))

        buf = io.StringIO()
        stream_succeeded = False
        completion_tokens = 0

        try:
            for token in provider.stream_response(
                message=user_prompt,
                user_id=user_id,
                conversation_id=conversation_id,
                model=model_name,
                system_prompt=system_prompt,
            ):
                buf.write(token)
                yield token

            completion_tokens = len(tokenizer.encode(buf.getvalue()))
            stream_succeeded = True

        # ------------- error branches ---------------------------------- #
        except ModelAccessError as err:
            self._log.warning(
                "Model access error: user=%s conv=%s model=%s provider=%s error=%s",
                user_id,
                conversation_id,
                model_name,
                provider_key,
                err,
            )
            if fallback_model and fallback_model not in _visited:
                self._log.info(
                    "Retrying with fallback model '%s' for user=%s conv=%s",
                    fallback_model,
                    user_id,
                    conversation_id,
                )
                yield from self.chat(
                    user_prompt, user_id, conversation_id, fallback_model, _visited
                )
                return
            raise

        except Exception as err:
            self._log.error(
                "Provider error: user=%s conv=%s model=%s provider=%s error=%s",
                user_id,
                conversation_id,
                model_name,
                provider_key,
                err,
            )
            raise

        finally:
            self._log.info(
                "AIStreamer: user=%s conv=%s model=%s elapsed=%.2f",
                user_id,
                conversation_id,
                model_name,
                time.monotonic() - start,
            )
            # Charge for whatever we successfully measured
            self._inc_usage(user_id, prompt_tokens + completion_tokens)

        # ---- Persist ASSISTANT only when full stream succeeded ------- #
        if stream_succeeded:
            assistant_text = buf.getvalue()
            if assistant_text:
                self._persist.save_assistant(
                    conversation_id, assistant_text, model_name
                )
