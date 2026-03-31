#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys


def _ensure_repo_venv() -> None:
    root = Path(__file__).resolve().parent.parent
    venv_dir = root / ".venv"
    venv_python = venv_dir / "bin" / "python"
    current_prefix = Path(sys.prefix).resolve()

    if not venv_python.exists():
        return
    if current_prefix == venv_dir.resolve():
        return
    if os.environ.get("AGENT_WIRE_BRIDGE_VENV_REEXEC") == "1":
        return

    env = dict(os.environ)
    env["AGENT_WIRE_BRIDGE_VENV_REEXEC"] = "1"
    os.execve(str(venv_python), [str(venv_python), str(Path(__file__).resolve())], env)


_ensure_repo_venv()

from litellm.llms.anthropic.experimental_pass_through.responses_adapters.transformation import (
    LiteLLMAnthropicToResponsesAPIAdapter,
)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    fixture_path = root / "fixtures" / "anthropic-metadata-request.json"
    request = json.loads(fixture_path.read_text())

    adapter = LiteLLMAnthropicToResponsesAPIAdapter()
    response = adapter.translate_request(request)

    prompt_cache_key = response.get("prompt_cache_key")
    instructions = response.get("instructions", "")
    reasoning = response.get("reasoning") or {}

    assert prompt_cache_key == "device-fixed-123", prompt_cache_key
    assert "user" not in response, response.get("user")
    assert "safety_identifier" not in response, response.get("safety_identifier")
    assert "Base system text" in instructions, instructions
    assert "SessionStart hook additional context" in instructions, instructions
    assert reasoning.get("effort") == "xhigh", reasoning

    print(
        json.dumps(
            {
                "prompt_cache_key": prompt_cache_key,
                "has_user": "user" in response,
                "has_safety_identifier": "safety_identifier" in response,
                "reasoning": reasoning,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
