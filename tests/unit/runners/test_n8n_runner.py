import json

import httpx
import pytest

from ai_shop_helper_backend.runners.n8n import N8nRunner

N8N_URL = "http://localhost:5678"
RUNNER_REF = "blog_titles"
TASK_ID = "test-task-id-001"
CALLBACK_URL = "http://localhost:8080/api/v1/agent-runs/1/steps/1/callback"
INPUTS = {"business": "Coffee shop", "audience": "Adults"}


def _make_runner(handler: httpx.MockTransport) -> N8nRunner:
    return N8nRunner(transport=handler)


class TestN8nRunnerAsyncAck:
    async def test_async_ack_response_accepted_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.runners.n8n.settings.N8N_URL", N8N_URL)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(202, json={"accepted": True})

        runner = _make_runner(httpx.MockTransport(handler))
        result = await runner.start(
            runner_ref=RUNNER_REF,
            inputs=INPUTS,
            task_id=TASK_ID,
            callback_url=CALLBACK_URL,
        )

        assert result.accepted is True
        assert result.status_code == 202
        assert result.sync_output is None
        assert result.external_ref == TASK_ID
        assert result.error is None

    async def test_async_ack_response_sync_output_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.runners.n8n.settings.N8N_URL", N8N_URL)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(202, json={"accepted": True})

        runner = _make_runner(httpx.MockTransport(handler))
        result = await runner.start(
            runner_ref=RUNNER_REF,
            inputs=INPUTS,
            task_id=TASK_ID,
            callback_url=CALLBACK_URL,
        )

        assert result.sync_output is None


class TestN8nRunnerSyncFinalResponse:
    async def test_sync_final_response_populates_sync_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.runners.n8n.settings.N8N_URL", N8N_URL)

        final_body = {"success": True, "data": {"context_titles": ["Title A", "Title B"]}}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=final_body)

        runner = _make_runner(httpx.MockTransport(handler))
        result = await runner.start(
            runner_ref=RUNNER_REF,
            inputs=INPUTS,
            task_id=TASK_ID,
            callback_url=CALLBACK_URL,
        )

        assert result.accepted is True
        assert result.sync_output == final_body
        assert result.external_ref == TASK_ID

    async def test_sync_final_response_with_title_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.runners.n8n.settings.N8N_URL", N8N_URL)

        final_body = {"title": "My Blog Post", "url_post": "https://example.com/post"}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=final_body)

        runner = _make_runner(httpx.MockTransport(handler))
        result = await runner.start(
            runner_ref=RUNNER_REF,
            inputs=INPUTS,
            task_id=TASK_ID,
            callback_url=CALLBACK_URL,
        )

        assert result.sync_output == final_body


class TestN8nRunnerErrors:
    async def test_n8n_500_returns_accepted_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.runners.n8n.settings.N8N_URL", N8N_URL)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="internal server error")

        runner = _make_runner(httpx.MockTransport(handler))
        result = await runner.start(
            runner_ref=RUNNER_REF,
            inputs=INPUTS,
            task_id=TASK_ID,
            callback_url=CALLBACK_URL,
        )

        assert result.accepted is False
        assert result.status_code == 500
        assert result.error is not None
        assert result.sync_output is None

    async def test_transport_error_returns_accepted_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.runners.n8n.settings.N8N_URL", N8N_URL)

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        runner = _make_runner(httpx.MockTransport(handler))
        result = await runner.start(
            runner_ref=RUNNER_REF,
            inputs=INPUTS,
            task_id=TASK_ID,
            callback_url=CALLBACK_URL,
        )

        assert result.accepted is False
        assert result.status_code == 0
        assert result.error is not None
        assert result.external_ref == TASK_ID


class TestN8nRunnerPostShape:
    async def test_post_url_is_n8n_url_webhook_runner_ref(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.runners.n8n.settings.N8N_URL", N8N_URL)

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(202, json={"accepted": True})

        runner = _make_runner(httpx.MockTransport(handler))
        await runner.start(
            runner_ref=RUNNER_REF,
            inputs=INPUTS,
            task_id=TASK_ID,
            callback_url=CALLBACK_URL,
        )

        assert len(captured) == 1
        assert str(captured[0].url) == f"{N8N_URL}/webhook/{RUNNER_REF}"

    async def test_post_body_includes_task_id_callback_url_and_inputs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("ai_shop_helper_backend.runners.n8n.settings.N8N_URL", N8N_URL)

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(202, json={"accepted": True})

        runner = _make_runner(httpx.MockTransport(handler))
        await runner.start(
            runner_ref=RUNNER_REF,
            inputs=INPUTS,
            task_id=TASK_ID,
            callback_url=CALLBACK_URL,
        )

        body = json.loads(captured[0].content)
        assert body["task_id"] == TASK_ID
        assert body["callback_url"] == CALLBACK_URL
        assert body["business"] == INPUTS["business"]
        assert body["audience"] == INPUTS["audience"]
