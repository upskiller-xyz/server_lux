"""Unit tests for the request-entry GPU prewarm wiring in EndpointRequestHandler."""

import pytest

from src.server import request_handler
from src.server.request_handler import EndpointRequestHandler
from src.server.enums import EndpointType


@pytest.fixture
def handler(monkeypatch):
    """Handler with all downstream steps stubbed so handle() only exercises wiring."""
    h = EndpointRequestHandler()
    monkeypatch.setattr(h._request_parser, "extract_params", lambda req: {})
    monkeypatch.setattr(h._request_parser, "extract_file", lambda req: None)
    monkeypatch.setattr(h._endpoint_controller, "run", lambda e, p, f: {"ok": True})
    monkeypatch.setattr(h._response_builder, "build", lambda result: ("resp", 200))
    return h


@pytest.fixture
def prewarm_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(request_handler.ModelPrewarmer, "prewarm", lambda: calls.append(True))
    return calls


@pytest.mark.parametrize("endpoint", [EndpointType.RUN, EndpointType.RUN_DETAILED])
def test_inference_endpoints_trigger_prewarm(handler, prewarm_calls, monkeypatch, endpoint):
    monkeypatch.setattr(handler._request_parser, "extract_endpoint", lambda req: endpoint)
    handler.handle(request=object())
    assert prewarm_calls == [True]


@pytest.mark.parametrize("endpoint", [EndpointType.ZENITH, EndpointType.HORIZON])
def test_non_inference_endpoints_do_not_prewarm(handler, prewarm_calls, monkeypatch, endpoint):
    monkeypatch.setattr(handler._request_parser, "extract_endpoint", lambda req: endpoint)
    handler.handle(request=object())
    assert prewarm_calls == []
