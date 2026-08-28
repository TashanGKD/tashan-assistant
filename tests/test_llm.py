import asyncio

import pytest

from app.config import settings
from app.llm import LLMClient


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "模型回答"}}]}


class FakeAsyncClient:
    captured = {}

    def __init__(self, *, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, *, headers, json):
        self.captured.update(url=url, headers=headers, json=json)
        return FakeResponse()


def test_llm_uses_env_configured_url_key_and_model(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_url", "https://llm.example/v1/chat/completions")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    monkeypatch.setattr("app.llm.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.captured = {}

    answer = asyncio.run(
        LLMClient().respond(
            "只回答问题",
            [{"role": "user", "content": "你好"}],
            max_output_tokens=321,
        )
    )

    assert answer == "模型回答"
    assert FakeAsyncClient.captured["url"] == "https://llm.example/v1/chat/completions"
    assert FakeAsyncClient.captured["headers"]["Authorization"] == "Bearer test-key"
    assert FakeAsyncClient.captured["json"] == {
        "model": "test-model",
        "messages": [
            {"role": "system", "content": "只回答问题"},
            {"role": "user", "content": "你好"},
        ],
        "max_tokens": 321,
    }


def test_llm_rejects_incomplete_configuration(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_url", "")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "")

    with pytest.raises(RuntimeError, match="LLM_API_URL"):
        asyncio.run(LLMClient().respond("system", "question"))


def test_strip_json_fence():
    content = '```json\n{"category":"环境配置"}\n```'
    assert LLMClient._strip_json_fence(content) == '{"category":"环境配置"}'
