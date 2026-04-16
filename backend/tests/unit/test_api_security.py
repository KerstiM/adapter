"""Security-focused tests for the stdlib HTTP API.

We spin up the real ``HTTPServer`` on an ephemeral port (loopback only) and
fire requests via the low-level ``http.client`` API so we can craft headers
exactly (``urllib`` insists on overriding Content-Length). Only the failure
paths are exercised, so the pipeline never actually runs and tests stay fast.
"""
from __future__ import annotations

import http.client
import json
import os
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

import pytest

from entrypoints import api as api_module


@pytest.fixture()
def server():
    httpd = HTTPServer(("127.0.0.1", 0), api_module.Handler)
    host, port = httpd.server_address
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield (host, port, f"http://{host}:{port}")
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def _raw_post(host: str, port: int, path: str, *, body: bytes,
              headers: dict | None = None,
              content_length_override: str | None = None):
    """POST with full control over the Content-Length header.

    If ``content_length_override`` is provided, that exact string is sent
    on the wire (even if it does not match ``len(body)``) so we can probe
    the server's validation.
    """
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.putrequest("POST", path, skip_host=False, skip_accept_encoding=True)
    if content_length_override is not None:
        conn.putheader("Content-Length", content_length_override)
    else:
        conn.putheader("Content-Length", str(len(body)))
    for k, v in (headers or {}).items():
        conn.putheader(k, v)
    conn.endheaders(message_body=body)
    resp = conn.getresponse()
    return resp.status, resp.read()


def test_oversize_body_returns_413(server):
    host, port, _ = server
    # Declare a huge Content-Length; the handler must short-circuit
    # before reading the body.
    status, body = _raw_post(
        host, port, "/api/run",
        body=b"{}",
        headers={"Content-Type": "application/json"},
        content_length_override=str(api_module.MAX_BODY_BYTES + 1),
    )
    assert status == 413
    assert json.loads(body)["error"] == "payload too large"


def test_invalid_json_returns_400(server):
    host, port, _ = server
    status, body = _raw_post(host, port, "/api/run", body=b"not-json",
                             headers={"Content-Type": "application/json"})
    assert status == 400
    assert json.loads(body)["error"] == "invalid json"


def test_invalid_content_length_returns_400(server):
    host, port, _ = server
    status, body = _raw_post(host, port, "/api/run", body=b"{}",
                             content_length_override="not-a-number")
    assert status == 400
    assert "Content-Length" in json.loads(body)["error"]


def test_negative_content_length_returns_400(server):
    host, port, _ = server
    status, body = _raw_post(host, port, "/api/run", body=b"",
                             content_length_override="-1")
    assert status == 400


def test_oversize_preamble_returns_400(server):
    host, port, _ = server
    payload = json.dumps({
        "datasetId": "D1",
        "llmPreamble": "A" * (api_module.MAX_PREAMBLE_CHARS + 1),
    }).encode()
    status, body = _raw_post(host, port, "/api/run", body=payload,
                             headers={"Content-Type": "application/json"})
    assert status == 400
    assert "llmPreamble too long" in json.loads(body)["error"]


def test_preamble_must_be_string(server):
    host, port, _ = server
    payload = json.dumps({"datasetId": "D1", "llmPreamble": 12345}).encode()
    status, body = _raw_post(host, port, "/api/run", body=payload,
                             headers={"Content-Type": "application/json"})
    assert status == 400


def test_unknown_dataset_does_not_leak_internals(server):
    host, port, _ = server
    payload = json.dumps({"datasetId": "DOES_NOT_EXIST"}).encode()
    status, body = _raw_post(host, port, "/api/run", body=payload,
                             headers={"Content-Type": "application/json"})
    assert status == 404
    err = json.loads(body)["error"]
    assert "DOES_NOT_EXIST" in err
    assert "Traceback" not in err
    assert "/home/" not in err


def test_cors_only_allowed_origins_get_header(server):
    _, _, base = server
    # Disallowed origin → no Access-Control-Allow-Origin header.
    req = urllib.request.Request(base + "/api/datasets")
    req.add_header("Origin", "https://evil.example")
    resp = urllib.request.urlopen(req, timeout=5)
    assert resp.headers.get("Access-Control-Allow-Origin") is None

    # Allowed origin → header is echoed back, not "*".
    req = urllib.request.Request(base + "/api/datasets")
    req.add_header("Origin", "http://localhost:5173")
    resp = urllib.request.urlopen(req, timeout=5)
    assert resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
    assert resp.headers.get("Vary") == "Origin"


def test_cors_origin_allowlist_respects_env_var(server, monkeypatch):
    _, _, base = server
    monkeypatch.setenv("ADAPTER_CORS_ORIGINS", "https://my-trusted.example")
    req = urllib.request.Request(base + "/api/datasets")
    req.add_header("Origin", "https://my-trusted.example")
    resp = urllib.request.urlopen(req, timeout=5)
    assert resp.headers.get("Access-Control-Allow-Origin") == "https://my-trusted.example"


def test_options_preflight_returns_204(server):
    _, _, base = server
    req = urllib.request.Request(base + "/api/run", method="OPTIONS")
    req.add_header("Origin", "http://localhost:5173")
    resp = urllib.request.urlopen(req, timeout=5)
    assert resp.status == 204
    assert resp.headers.get("Access-Control-Allow-Methods") == "GET, POST, OPTIONS"


# ---------------------------------------------------------------------------
# rawContexts opt-in: counterparty/remittance text must not leak by default.
# ---------------------------------------------------------------------------

def test_llm_preview_omits_raw_contexts_by_default(tmp_path):
    proj = tmp_path / "projections"
    proj.mkdir()
    (proj / "llm_context_v1.json").write_text(json.dumps({
        "meta": {"iban": "EE000", "currency": "EUR"},
        "tx": [
            {"id": "T1", "d": "2024-01-01", "a": "-10.00",
             "dir": "DEBIT", "cp": "Real Counterparty Name",
             "r": "Sensitive remittance text"},
        ],
    }))

    preview = api_module._read_llm_preview(tmp_path)
    assert preview["rawContexts"] == [], "raw contexts must be empty when not opted in"
    serialised = json.dumps(preview)
    assert "Real Counterparty Name" not in serialised
    assert "Sensitive remittance text" not in serialised


def test_llm_preview_includes_raw_contexts_when_opted_in(tmp_path):
    proj = tmp_path / "projections"
    proj.mkdir()
    (proj / "llm_context_v1.json").write_text(json.dumps({
        "meta": {"iban": "EE000", "currency": "EUR"},
        "tx": [
            {"id": "T1", "d": "2024-01-01", "a": "-10.00",
             "dir": "DEBIT", "cp": "Real Counterparty Name",
             "r": "Sensitive remittance text"},
        ],
    }))

    preview = api_module._read_llm_preview(tmp_path, include_raw=True)
    assert len(preview["rawContexts"]) == 1
    assert preview["rawContexts"][0]["tx"][0]["cp"] == "Real Counterparty Name"
