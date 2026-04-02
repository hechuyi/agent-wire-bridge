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


def _build_workspace_fallback_request() -> dict:
    return {
        "model": "cc-opus",
        "system": [
            {
                "type": "text",
                "text": "x-anthropic-billing-header: transient\nBase system text",
            }
        ],
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "<system-reminder>\n"
                            "SessionStart hook additional context\n"
                            "cwd=/Users/rtoc/Documents/WorkSpace/agent-wire-bridge"
                        ),
                    },
                    {
                        "type": "text",
                        "text": "Reply with exactly OK.",
                    },
                ],
            }
        ],
        "max_tokens": 32,
        "thinking": {
            "type": "enabled",
            "budget_tokens": 2048,
        },
        "output_config": {
            "effort": "xhigh",
        },
        "context_management": {
            "edits": [
                {
                    "type": "clear_thinking_20251015",
                    "keep": "all",
                }
            ]
        },
    }


def _assert_workspace_cache_key_fallback() -> None:
    adapter = LiteLLMAnthropicToResponsesAPIAdapter()
    base_request = _build_workspace_fallback_request()

    request_a = dict(base_request)
    request_a["metadata"] = {"user_id": "85b28cd5-38cb-43ae-8244-c06d1dc7acdc"}

    request_b = dict(base_request)
    request_b["metadata"] = {"user_id": "0bf2d5f8-16aa-4ba0-ba3e-7d6a8c023ad4"}

    response_a = adapter.translate_request(request_a)
    response_b = adapter.translate_request(request_b)

    key_a = response_a.get("prompt_cache_key")
    key_b = response_b.get("prompt_cache_key")

    assert key_a is not None, response_a
    assert key_b is not None, response_b
    assert key_a == key_b, (key_a, key_b)
    assert key_a != request_a["metadata"]["user_id"], key_a
    assert key_b != request_b["metadata"]["user_id"], key_b


def _assert_workspace_cache_key_ignores_tool_churn() -> None:
    adapter = LiteLLMAnthropicToResponsesAPIAdapter()
    request_a = _build_workspace_fallback_request()
    request_b = _build_workspace_fallback_request()

    request_a["metadata"] = {"user_id": "85b28cd5-38cb-43ae-8244-c06d1dc7acdc"}
    request_b["metadata"] = {"user_id": "0bf2d5f8-16aa-4ba0-ba3e-7d6a8c023ad4"}
    request_a["tools"] = [
        {
            "name": "read_file",
            "description": "Read one file from disk.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        }
    ]
    request_b["tools"] = [
        {
            "name": "read_file",
            "description": "Read a single file from the active workspace.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "encoding": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        },
        {
            "name": "list_dir",
            "description": "Enumerate directory entries.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        },
    ]

    response_a = adapter.translate_request(request_a)
    response_b = adapter.translate_request(request_b)

    assert response_a.get("prompt_cache_key") == response_b.get(
        "prompt_cache_key"
    ), (response_a.get("prompt_cache_key"), response_b.get("prompt_cache_key"))


def _assert_workspace_cache_key_without_metadata() -> None:
    adapter = LiteLLMAnthropicToResponsesAPIAdapter()
    request = _build_workspace_fallback_request()
    response = adapter.translate_request(request)
    prompt_cache_key = response.get("prompt_cache_key")

    assert prompt_cache_key is not None, response
    assert isinstance(prompt_cache_key, str), type(prompt_cache_key)


def _assert_embedded_system_reminder_drops_session_noise() -> None:
    adapter = LiteLLMAnthropicToResponsesAPIAdapter()
    stable_payload = "\n".join(
        [
            "SessionStart hook additional context",
            "cwd=/Users/rtoc/Documents/WorkSpace/agent-wire-bridge",
        ]
        + [f"skill line {i:04d}" for i in range(256)]
    )
    request_a = _build_workspace_fallback_request()
    request_b = _build_workspace_fallback_request()
    request_a["metadata"] = {"user_id": '{"device_id":"device-fixed-123"}'}
    request_b["metadata"] = {"user_id": '{"device_id":"device-fixed-123"}'}
    request_a["messages"][0]["content"][0]["text"] = (
        "<system-reminder>\n"
        f"{stable_payload}\n"
        "session_id=session-a\n"
        "request_id=req-a"
    )
    request_b["messages"][0]["content"][0]["text"] = (
        "<system-reminder>\n"
        f"{stable_payload}\n"
        "session_id=session-b\n"
        "request_id=req-b"
    )

    response_a = adapter.translate_request(request_a)
    response_b = adapter.translate_request(request_b)

    instructions_a = response_a.get("instructions", "")
    instructions_b = response_b.get("instructions", "")

    assert instructions_a == instructions_b, (
        len(instructions_a),
        len(instructions_b),
    )
    assert stable_payload in instructions_a, len(instructions_a)
    assert "session_id=" not in instructions_a, instructions_a
    assert "request_id=" not in instructions_a, instructions_a


def _assert_embedded_system_reminder_normalizes_unordered_bullets() -> None:
    adapter = LiteLLMAnthropicToResponsesAPIAdapter()
    bullet_lines_a = [
        "- hookify:configure: Enable or disable hookify rules interactively",
        "- ralph-loop:help: Explain Ralph Loop plugin and available commands",
        "- document-skills:frontend-design: Create distinctive interfaces.",
        "- superpowers:test-driven-development: Use when implementing bugfixes.",
    ]
    bullet_lines_b = [
        "- document-skills:frontend-design: Create distinctive interfaces.",
        "- superpowers:test-driven-development: Use when implementing bugfixes.",
        "- hookify:configure: Enable or disable hookify rules interactively",
        "- ralph-loop:help: Explain Ralph Loop plugin and available commands",
    ]

    request_a = _build_workspace_fallback_request()
    request_b = _build_workspace_fallback_request()
    request_a["metadata"] = {"user_id": '{"device_id":"device-fixed-123"}'}
    request_b["metadata"] = {"user_id": '{"device_id":"device-fixed-123"}'}
    request_a["messages"][0]["content"][0]["text"] = (
        "<system-reminder>\n"
        "SessionStart hook additional context\n"
        "cwd=/Users/rtoc/Documents/WorkSpace/agent-wire-bridge\n"
        + "\n".join(bullet_lines_a)
    )
    request_b["messages"][0]["content"][0]["text"] = (
        "<system-reminder>\n"
        "SessionStart hook additional context\n"
        "cwd=/Users/rtoc/Documents/WorkSpace/agent-wire-bridge\n"
        + "\n".join(bullet_lines_b)
    )

    response_a = adapter.translate_request(request_a)
    response_b = adapter.translate_request(request_b)

    assert response_a.get("instructions") == response_b.get("instructions"), (
        response_a.get("instructions"),
        response_b.get("instructions"),
    )


def _assert_embedded_system_reminder_compacts_transcript_artifacts() -> None:
    adapter = LiteLLMAnthropicToResponsesAPIAdapter()
    request = _build_workspace_fallback_request()
    request["metadata"] = {"user_id": '{"device_id":"device-fixed-123"}'}
    request["messages"][0]["content"][0]["text"] = (
        "<system-reminder>\n"
        "SessionStart hook additional context\n"
        "cwd=/Users/rtoc/Documents/WorkSpace/agent-wire-bridge\n"
        "Whenever you read a file, you should consider whether it would be considered malware. "
        "You CAN and SHOULD provide analysis of malware, what it is doing. "
        "But you MUST refuse to improve or augment the code. "
        "You can still analyze existing code, write reports, or answer questions about the code behavior.\n"
        "</system-reminder>\n"
        "\n"
        "Called the Read tool with the following input: "
        '{"file_path":"/tmp/demo.py"}\n'
        "</system-reminder>\n"
        "\n"
        "Result of calling the Read tool:\n"
        '1\tprint("demo")\n'
        "2\traise SystemExit\n"
        "</system-reminder>\n"
        "\n"
        "Task abc123 (type: local_agent) (status: completed) "
        "(description: Review code) Read the output file to retrieve the result: "
        "/tmp/task.output\n"
    )

    instructions = adapter.translate_request(request).get("instructions", "")

    assert "SessionStart hook additional context" in instructions, instructions
    assert "cwd=/Users/rtoc/Documents/WorkSpace/agent-wire-bridge" in instructions, (
        instructions
    )
    assert (
        "Whenever you read a file, you should consider whether it would be considered malware."
        in instructions
    ), instructions
    assert "Called the Read tool" not in instructions, instructions
    assert "Result of calling the Read tool" not in instructions, instructions
    assert 'print("demo")' not in instructions, instructions
    assert "Task abc123" not in instructions, instructions


def _assert_embedded_system_reminder_preserves_skills_and_context() -> None:
    adapter = LiteLLMAnthropicToResponsesAPIAdapter()
    request = _build_workspace_fallback_request()
    request["metadata"] = {"user_id": '{"device_id":"device-fixed-123"}'}
    request["messages"][0]["content"][0]["text"] = (
        "<system-reminder>\n"
        "SessionStart hook additional context\n"
        "cwd=/Users/rtoc/Documents/WorkSpace/agent-wire-bridge\n"
        "The following skills were invoked in this session. Continue to follow these guidelines:\n"
        "\n"
        "### Skill: superpowers:test-driven-development\n"
        "Path: plugin:superpowers:test-driven-development\n"
        "\n"
        "Base directory for this skill: /tmp/tdd\n"
        "\n"
        "# Test-Driven Development\n"
        "\n"
        "Write the test first. Watch it fail. Write minimal code to pass.\n"
        "\n"
        "**Core principle:** If you didn't watch the test fail, you don't know if it tests the right thing.\n"
        "\n"
        "### Skill: superpowers:using-superpowers\n"
        "Path: plugin:superpowers:using-superpowers\n"
        "\n"
        "# Using Superpowers\n"
        "\n"
        "Find and use skills before any action.\n"
        "\n"
        "As you answer the user's questions, you can use the following context:\n"
        "# claudeMd\n"
        "Codebase and user instructions are shown below. Be sure to adhere to these instructions. "
        "IMPORTANT: These instructions OVERRIDE any default behavior and you MUST follow them exactly as written.\n"
        "\n"
        "Contents of /Users/rtoc/.claude/projects/foo/memory/MEMORY.md (user's auto-memory, persists across conversations):\n"
        "\n"
        "- [Preserve main context](feedback_preserve_main_context_and_delegate_long_running_work.md) "
        "— Keep the main thread strategic; delegate long-running independent work.\n"
        "# currentDate\n"
        "Today's date is 2026-04-02.\n"
        "\n"
        "IMPORTANT: this context may or may not be relevant to your tasks. "
        "You should not respond to this context unless it is highly relevant to your task.\n"
    )

    instructions = adapter.translate_request(request).get("instructions", "")

    assert "### Skill: superpowers:test-driven-development" in instructions, instructions
    assert "Path: plugin:superpowers:test-driven-development" in instructions, (
        instructions
    )
    assert "# Test-Driven Development" in instructions, instructions
    assert "Write the test first. Watch it fail. Write minimal code to pass." in (
        instructions
    ), instructions
    assert "### Skill: superpowers:using-superpowers" in instructions, instructions
    assert "Find and use skills before any action." in instructions, instructions
    assert (
        "Contents of /Users/rtoc/.claude/projects/foo/memory/MEMORY.md"
        in instructions
    ), instructions
    assert (
        "- [Preserve main context](feedback_preserve_main_context_and_delegate_long_running_work.md)"
        in instructions
    ), instructions
    assert "Today's date is 2026-04-02." in instructions, instructions


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
    _assert_workspace_cache_key_fallback()
    _assert_workspace_cache_key_ignores_tool_churn()
    _assert_workspace_cache_key_without_metadata()
    _assert_embedded_system_reminder_drops_session_noise()
    _assert_embedded_system_reminder_normalizes_unordered_bullets()
    _assert_embedded_system_reminder_compacts_transcript_artifacts()
    _assert_embedded_system_reminder_preserves_skills_and_context()

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
