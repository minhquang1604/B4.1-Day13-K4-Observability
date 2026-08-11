from __future__ import annotations

import json

from app import agent as agent_module
from app.pii import hash_user_id


class ManagedPrompt:
    version = 1

    def compile(self, **variables: str) -> str:
        return (
            f"Feature={variables['feature']}\n"
            f"Docs={variables['docs']}\n"
            f"Question={variables['message']}"
        )


class RecordingLangfuseClient:
    def __init__(self) -> None:
        self.prompt = ManagedPrompt()
        self.trace_updates: list[dict] = []
        self.generation_updates: list[dict] = []

    def get_prompt(self, name: str, **kwargs):
        return self.prompt

    def update_current_trace(self, **kwargs) -> None:
        self.trace_updates.append(kwargs)

    def update_current_generation(self, **kwargs) -> None:
        self.generation_updates.append(kwargs)


def test_trace_and_generation_metadata_do_not_leak_raw_pii(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "test-public-key")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("LANGFUSE_PROMPT_NAME", "day13-chat")
    monkeypatch.setenv("LANGFUSE_PROMPT_LABEL", "production")

    client = RecordingLangfuseClient()
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)

    raw_user_id = "raw-user-42"
    raw_email = "student@vinuni.edu.vn"
    raw_phone = "0987654321"
    message = f"My email is {raw_email} and my phone is {raw_phone}"

    agent = agent_module.LabAgent()
    # Gọi thẳng hàm gốc (__wrapped__) để bỏ qua decorator @observe thật của
    # Langfuse SDK (tránh gọi mạng trong test), giống pattern ở
    # test_agent_prompt_trace.py.
    agent_module.LabAgent.run.__wrapped__(
        agent,
        user_id=raw_user_id,
        feature="qa",
        session_id="session-01",
        message=message,
    )

    trace_update = client.trace_updates[-1]
    generation_update = client.generation_updates[-1]

    # user_id gửi lên trace phải là bản hash, không phải raw user_id.
    assert trace_update["user_id"] == hash_user_id(raw_user_id)

    # Không có raw PII/raw user_id nào lọt vào payload gửi lên Langfuse.
    serialized = json.dumps(trace_update, default=str) + json.dumps(
        generation_update, default=str
    )
    assert raw_user_id not in serialized
    assert raw_email not in serialized
    assert raw_phone not in serialized

    # query_preview phải là bản đã redact, không phải message gốc.
    query_preview = generation_update["metadata"]["query_preview"]
    assert raw_email not in query_preview
    assert raw_phone not in query_preview
    assert "REDACTED_EMAIL" in query_preview
    assert "REDACTED_PHONE_VN" in query_preview


def test_observe_decorator_disables_raw_input_output_capture() -> None:
    # Guard tĩnh: nếu ai đó vô tình xoá capture_input=False/capture_output=False,
    # Langfuse SDK sẽ tự động log nguyên văn message/answer (PII) vào trace.
    from pathlib import Path

    agent_source = Path(agent_module.__file__).read_text(encoding="utf-8")
    assert "capture_input=False" in agent_source
    assert "capture_output=False" in agent_source
