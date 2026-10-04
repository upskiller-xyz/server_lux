"""Tests for [call]-record persistence: buffer, daily file, rotation-safe paths.

The store exists because stdout dies with the container: a deploy is
``up -d --force-recreate``, which wipes the records exactly when they matter
(before/after a deploy comparison). These tests pin the contract the reduce
step depends on — file-name shape, one JSON object per line, today's file
never uploaded, failed writes retried — without touching the network.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.server.env_keys import EnvKey
from src.server.services.helpers.call_record_store import (
    CallRecordBuffer,
    CallRecordPath,
    CallRecordStore,
    DayFileUploader,
    DayFileWriter,
)


class _FakeUploader:
    """Records what a real uploader would send — no network in tests."""

    def __init__(self):
        self.uploaded = []

    def upload_file(self, path, bucket, key):
        self.uploaded.append((path, bucket, key))


class TestCallRecordPath:

    def test_daily_file_name_carries_the_utc_date(self):
        day = datetime(2026, 10, 4, tzinfo=timezone.utc)
        path = CallRecordPath.daily("/var/log/lux/call-records", day)
        assert path == Path("/var/log/lux/call-records/calls-2026-10-04.jsonl")


class TestCallRecordBuffer:

    def test_drain_returns_and_clears(self):
        buffer = CallRecordBuffer()
        buffer.append({"a": 1})
        buffer.append({"b": 2})
        assert buffer.drain() == [{"a": 1}, {"b": 2}]
        assert buffer.drain() == []


class TestDayFileWriter:

    def test_appends_one_json_object_per_line(self, tmp_path):
        writer = DayFileWriter(str(tmp_path))
        writer.write([{"rid": "x", "ms": 1.0}, {"rid": "y", "ms": 2.0}])
        writer.write([{"rid": "z", "ms": 3.0}])

        path = CallRecordPath.daily(
            str(tmp_path), datetime.now(timezone.utc)
        )
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert [json.loads(line)["rid"] for line in lines] == ["x", "y", "z"]

    def test_empty_flush_creates_nothing(self, tmp_path):
        writer = DayFileWriter(str(tmp_path))
        writer.write([])
        path = CallRecordPath.daily(str(tmp_path), datetime.now(timezone.utc))
        assert not path.exists()


class TestDayFileUploader:

    def test_uploads_yesterdays_file_not_todays(self, tmp_path):
        today = datetime.now(timezone.utc)
        writer = DayFileWriter(str(tmp_path))
        writer.write([{"rid": "today"}])

        yesterday_path = CallRecordPath.daily(str(tmp_path), today - timedelta(days=1))
        yesterday_path.write_text('{"rid": "yesterday"}\n', encoding="utf-8")

        fake = _FakeUploader()
        uploader = DayFileUploader("bucket", str(tmp_path), client=fake)
        uploader.upload_previous_day()

        # Only the closed day reaches the bucket: today's file is still open.
        assert len(fake.uploaded) == 1
        path, bucket, key = fake.uploaded[0]
        assert path == str(yesterday_path)
        assert bucket == "bucket"
        assert key == yesterday_path.name

    def test_missing_yesterday_is_silent(self, tmp_path):
        fake = _FakeUploader()
        uploader = DayFileUploader("bucket", str(tmp_path), client=fake)
        uploader.upload_previous_day()  # no file — must not raise
        assert fake.uploaded == []


class TestCallRecordStore:

    def test_record_without_configured_store_is_a_noop(self):
        # Before configure() (or with no bucket configured) the recorder must
        # not crash on CallRecordStore.record().
        CallRecordStore.record({"rid": "x"})

    def test_flush_persists_records_and_retries_after_write_error(self, tmp_path, monkeypatch):
        store = CallRecordStore(str(tmp_path), bucket=None, flush_seconds=60)
        store._buffer.append({"rid": "first"})

        calls = {"n": 0}

        def flaky_write(records):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("disk full")
            return DayFileWriter(str(tmp_path)).write(records)

        monkeypatch.setattr(store._writer, "write", flaky_write)
        store.flush()
        # First flush failed — records back in the buffer, not lost.
        monkeypatch.setattr(store._writer, "write", DayFileWriter(str(tmp_path)).write)
        store.flush()

        path = CallRecordPath.daily(str(tmp_path), datetime.now(timezone.utc))
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert [json.loads(line)["rid"] for line in lines] == ["first"]

    def test_configure_without_bucket_leaves_store_absent(self, monkeypatch):
        monkeypatch.delenv(EnvKey.CALL_RECORDS_BUCKET.value, raising=False)
        monkeypatch.setattr(CallRecordStore, "_instance", None)
        CallRecordStore.configure()
        assert CallRecordStore._instance is None