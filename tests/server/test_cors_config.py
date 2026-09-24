"""CORS policy built from CORS_ORIGINS."""

import pytest
from flask import Flask

from src.server.cors_config import CORS_ORIGINS_ENV, CorsConfig

WEB_ORIGIN = "https://app.example.com"


def _client(monkeypatch, origins: str):
    monkeypatch.setenv(CORS_ORIGINS_ENV, origins)
    app = Flask(__name__)
    CorsConfig.from_environment().apply(app)
    app.add_url_rule("/v1/run", "run", lambda: ("ok", 200, {"X-RateLimit-Remaining": "3"}), methods=["POST"])
    return app.test_client()


def test_parses_and_normalises_origins(monkeypatch):
    monkeypatch.setenv(CORS_ORIGINS_ENV, f" {WEB_ORIGIN}/ , https://b.example.com")
    assert CorsConfig.from_environment().origins == (WEB_ORIGIN, "https://b.example.com")


@pytest.mark.parametrize("raw", ["", "  ", ","])
def test_unset_falls_back_to_allow_all(monkeypatch, raw):
    monkeypatch.setenv(CORS_ORIGINS_ENV, raw)
    assert CorsConfig.from_environment().allows_all


def test_allowed_origin_gets_cors_headers_and_exposed_quota(monkeypatch):
    response = _client(monkeypatch, WEB_ORIGIN).post("/v1/run", headers={"Origin": WEB_ORIGIN})
    assert response.headers["Access-Control-Allow-Origin"] == WEB_ORIGIN
    assert "X-RateLimit-Remaining" in response.headers["Access-Control-Expose-Headers"]
    assert "Access-Control-Allow-Credentials" not in response.headers


def test_foreign_origin_gets_no_cors_headers(monkeypatch):
    response = _client(monkeypatch, WEB_ORIGIN).post("/v1/run", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in response.headers
