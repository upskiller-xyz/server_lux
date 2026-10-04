"""Tests for the [call] tracing records.

One JSON line per outbound remote-service call: service name from the
``ServiceName`` enum (never parsed from the URL), correlation id from the
request context, outcome and wall time. These records are what the reduce
step reads, so their shape is contract — the keys and outcomes are asserted
field by field here rather than as one opaque dict.
"""

import asyncio
import json
import logging
import threading

from flask import Flask, jsonify, make_response

from src.server.enums import HTTPHeader, ServiceName
from src.server.services.helpers.call_recorder import (
    UNKNOWN_REQUEST_ID,
    CallOutcome,
    CallRecord,
    CallRecorder,
    RequestIdContext,
    RequestIdMiddleware,
)
from src.server.telemetry import MAX_HEADER_VALUE_LENGTH


def _records(caplog):
    return [
        json.loads(r.message.split(" ", 1)[1])
        for r in caplog.records
        if r.message.startswith("[call] ")
    ]


class TestCallRecorder:

    def test_ok_call_emits_one_record_with_contract_fields(self, caplog):
        with caplog.at_level(logging.INFO, logger="logger"):
            with CallRecorder(ServiceName.ENCODER, "/encode"):
                pass

        records = _records(caplog)
        assert len(records) == 1
        record = records[0]
        assert record[CallRecord.SERVICE] == "encoder"
        assert record[CallRecord.ENDPOINT] == "/encode"
        assert record[CallRecord.OUTCOME] == CallOutcome.OK
        assert isinstance(record[CallRecord.MS], float)
        assert isinstance(record[CallRecord.TS], float)

    def test_service_name_is_the_enum_value_not_a_url_segment(self, caplog):
        # _parse_service_name(url) would mislabel this URL "predict"; the
        # record must carry the enum's value instead.
        with caplog.at_level(logging.INFO, logger="logger"):
            with CallRecorder(ServiceName.MODEL, "/predict"):
                pass

        assert _records(caplog)[0][CallRecord.SERVICE] == "model"

    def test_error_outcome_recorded_and_exception_propagates(self, caplog):
        with caplog.at_level(logging.INFO, logger="logger"):
            try:
                with CallRecorder(ServiceName.OBSTRUCTION, "/obstruction"):
                    raise ValueError("boom")
            except ValueError:
                pass

        records = _records(caplog)
        assert len(records) == 1
        assert records[0][CallRecord.OUTCOME] == CallOutcome.ERROR

    def test_rid_defaults_to_unknown_without_a_request(self, caplog):
        with caplog.at_level(logging.INFO, logger="logger"):
            with CallRecorder(ServiceName.MERGER, "merge"):
                pass

        assert _records(caplog)[0][CallRecord.RID] == UNKNOWN_REQUEST_ID

    def test_wait_ms_stamped_when_recorded_and_absent_when_not(self, caplog):
        with caplog.at_level(logging.INFO, logger="logger"):
            with CallRecorder(ServiceName.OBSTRUCTION, "obstruction_parallel_bin") as recorder:
                recorder.record_wait(1234.5)
            with CallRecorder(ServiceName.ENCODER, "encode"):
                pass

        stamped, unstamped = _records(caplog)
        assert stamped[CallRecord.WAIT_MS] == 1234.5
        # Missing key, not 0: "no gate" and "instant gate" stay distinguishable.
        assert CallRecord.WAIT_MS not in unstamped


class TestRequestIdContext:

    def test_set_and_get_round_trip(self):
        token = RequestIdContext.set("abc123")
        try:
            assert RequestIdContext.get() == "abc123"
        finally:
            RequestIdContext.reset(token)
        assert RequestIdContext.get() == UNKNOWN_REQUEST_ID

    def test_contextvar_survives_into_worker_threads(self):
        # The fan-out runs service calls via asyncio.to_thread; the id must
        # follow into the worker. (A plain threading.Thread does NOT inherit
        # contextvars — documented in the test below — which is exactly why
        # the fan-out uses to_thread and not run_in_executor.)
        token = RequestIdContext.set("thread-id-1")
        try:
            seen = asyncio.run(asyncio.to_thread(RequestIdContext.get))
            assert seen == "thread-id-1"
        finally:
            RequestIdContext.reset(token)

    def test_plain_thread_does_not_inherit_later_sets(self):
        # Documents the boundary the to_thread switch depends on: a thread
        # spawned from a context that has not had the id set sees the default.
        # This is why run_in_executor (which does not copy the context) was
        # broken for correlation, and why the fan-out must use to_thread.
        seen = []
        thread = threading.Thread(target=lambda: seen.append(RequestIdContext.get()))
        thread.start()
        thread.join()
        assert seen == [UNKNOWN_REQUEST_ID]


class TestRequestIdMiddleware:

    def _app(self):
        app = Flask(__name__)
        RequestIdMiddleware().register(app)

        @app.route("/ping")
        def ping():
            return jsonify({"rid": RequestIdContext.get()})

        return app

    def test_reads_header_into_context_and_echoes_on_response(self):
        client = self._app().test_client()
        response = client.get("/ping", headers={HTTPHeader.REQUEST_ID.value: "rid-42"})

        assert response.get_json()["rid"] == "rid-42"
        assert response.headers[HTTPHeader.REQUEST_ID.value] == "rid-42"

    def test_unprintable_characters_stripped_from_hostile_header(self):
        # Werkzeug refuses raw CR/LF in a test request context (as a real
        # server would on the wire), so use an ESC control character — the
        # sanitizer must strip it either way.
        client = self._app().test_client()
        response = client.get("/ping", headers={HTTPHeader.REQUEST_ID.value: "a\x1bb"})

        rid = response.get_json()["rid"]
        assert "\x1b" not in rid
        assert rid == "ab"

    def test_control_only_header_falls_back_to_unknown(self):
        client = self._app().test_client()
        response = client.get("/ping", headers={HTTPHeader.REQUEST_ID.value: "\x1b\x7f"})

        assert response.get_json()["rid"] == UNKNOWN_REQUEST_ID

    def test_amplifying_header_value_is_truncated(self):
        # The rid is copied into every [call] record and the per-window fan-out
        # multiplies that, so a megabyte header must not reach the log.
        client = self._app().test_client()
        response = client.get("/ping", headers={HTTPHeader.REQUEST_ID.value: "x" * (MAX_HEADER_VALUE_LENGTH * 10)})

        assert len(response.get_json()["rid"]) == MAX_HEADER_VALUE_LENGTH

    def test_missing_header_falls_back_to_unknown(self):
        client = self._app().test_client()
        response = client.get("/ping")

        assert response.get_json()["rid"] == UNKNOWN_REQUEST_ID

    def test_contextvar_reset_after_response(self):
        # The id must not survive the request: gunicorn reuses worker threads,
        # and a leaked id would stamp the next request's records. _capture
        # always sets, so a regression here would never surface without an
        # explicit assertion.
        client = self._app().test_client()
        assert RequestIdContext.get() == UNKNOWN_REQUEST_ID
        client.get("/ping", headers={HTTPHeader.REQUEST_ID.value: "leaky"})
        assert RequestIdContext.get() == UNKNOWN_REQUEST_ID

    def test_echo_tolerates_a_short_circuited_before_request(self):
        # A before_request that returns a response (auth guard, maintenance
        # mode) skips _capture, but after_request still runs — _echo must not
        # turn that into an AttributeError/500 on every request.
        app = Flask(__name__)
        RequestIdMiddleware().register(app)

        @app.before_request
        def _short_circuit():
            return make_response("maintenance", 503)

        response = app.test_client().get("/ping")
        assert response.status_code == 503