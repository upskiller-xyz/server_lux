"""Unit tests for RequestParser.extract_params (orjson body parsing + fallback)."""

import orjson
from flask import Flask, request

from src.server.request_handler import RequestParser

app = Flask(__name__)


def test_parses_json_body_via_orjson():
    body = orjson.dumps({"model_type": "df_default", "parameters": {"x": 1}})
    with app.test_request_context(data=body, content_type="application/json"):
        assert RequestParser.extract_params(request) == {
            "model_type": "df_default",
            "parameters": {"x": 1},
        }


def test_malformed_json_falls_back_to_form():
    with app.test_request_context(data=b"{not json", content_type="application/json"):
        # orjson raises → form fallback (no form fields here → empty dict).
        assert RequestParser.extract_params(request) == {}


def test_non_json_uses_form():
    with app.test_request_context(data={"a": "1", "b": "2"}):  # multipart/form-encoded
        assert RequestParser.extract_params(request) == {"a": "1", "b": "2"}
