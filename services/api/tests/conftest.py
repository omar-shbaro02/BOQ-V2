import urllib.request
from collections.abc import Generator

import httpx
import pytest
from app.config import get_settings


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live-adapters", action="store_true", help="Enable paid external-adapter tests"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        if item.get_closest_marker("live_adapter") and not config.getoption("--live-adapters"):
            item.add_marker(pytest.mark.skip(reason="Requires explicit --live-adapters opt-in"))


@pytest.fixture(autouse=True)
def isolate_external_adapters(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Generator[None, None, None]:
    """Keep the default test suite independent of developer credentials and network state."""

    live = request.node.get_closest_marker("live_adapter") and request.config.getoption(
        "--live-adapters"
    )
    monkeypatch.setenv("VAI_ENVIRONMENT", "test")
    if not live:
        monkeypatch.setenv("VAI_OPENAI_API_KEY", "")
        monkeypatch.setenv("VAI_OPENAI_AGENTS_ENABLED", "false")

        def deny_network(*args: object, **kwargs: object) -> None:
            raise AssertionError("External HTTP is disabled; use the opt-in live-adapter profile")

        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", deny_network)
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", deny_network)
        monkeypatch.setattr(urllib.request.OpenerDirector, "open", deny_network)
        from botocore.endpoint import Endpoint

        monkeypatch.setattr(Endpoint, "_send", deny_network)
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()
