import logging
import os


LOGGER = logging.getLogger("agent_wire_bridge.overrides")


def _truthy(name: str) -> bool:
    value = os.getenv(name, "")
    return value.lower() in {"1", "true", "yes", "on"}


def _disable_remote_openai_input_tokens() -> None:
    if not _truthy("LITELLM_DISABLE_OPENAI_RESPONSES_INPUT_TOKENS"):
        return

    try:
        from litellm.llms.openai.responses.count_tokens.token_counter import (
            OpenAITokenCounter,
        )
    except ImportError:
        return
    except Exception as exc:  # pragma: no cover - defensive startup guard
        LOGGER.warning("failed to import LiteLLM token counter override: %s", exc)
        return

    try:
        def _never_use_provider_api(self, custom_llm_provider=None) -> bool:
            return False

        OpenAITokenCounter.should_use_token_counting_api = _never_use_provider_api
    except Exception as exc:  # pragma: no cover - defensive startup guard
        LOGGER.warning(
            "failed to disable remote OpenAI input_tokens counting: %s", exc
        )


_disable_remote_openai_input_tokens()
