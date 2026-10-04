"""Persistence for ``[call]`` records: JSONL files, daily rotation, S3 upload.

stdout is ephemeral — a deploy recreates the container and the records are
gone, exactly when they matter most (before/after a deploy comparison). This
store gives them a home that survives deploys and the box itself, per the
observability plan's step 4:

- every record is appended to ``<dir>/calls-YYYY-MM-DD.jsonl`` (one file per
  day, UTC — the reduce step reads whole files, no offset parsing);
- a background flusher writes buffered records to disk every
  ``CALL_RECORDS_FLUSH_SECONDS`` and, when credentials are present, uploads
  the closed day's file to Scaleway Object Storage;
- never raises: persistence is best-effort, a lost record must not fail the
  request it measured.

The reduce step reads the bucket files directly (no API keys beyond the
bucket's own, no query language, no backend client) — a flat file over a
backend is deliberate at this volume (~8 runs/day).
"""
import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional

from ...env_keys import EnvKey

logger = logging.getLogger("logger")


class CallRecordPath:
    """File-name contract for the store — one place, so the writer, the
    uploader and any reduce script agree without sharing code."""

    TEMPLATE: str = "calls-{date}.jsonl"
    DATE_FORMAT: str = "%Y-%m-%d"
    DEFAULT_DIR: str = "/var/log/lux/call-records"

    @classmethod
    def daily(cls, directory: str, day: datetime) -> Path:
        name = cls.TEMPLATE.format(date=day.strftime(cls.DATE_FORMAT))
        return Path(directory) / name


class CallRecordBuffer:
    """Thread-safe in-memory buffer of records pending flush.

    The recorders run on worker threads (the fan-out), so appends come from
    many threads at once; flushes come from the background timer.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._records: List[dict] = []

    def append(self, record: dict) -> None:
        with self._lock:
            self._records.append(record)

    def drain(self) -> List[dict]:
        with self._lock:
            drained = self._records
            self._records = []
            return drained


class DayFileWriter:
    """Appends records to the current day's JSONL file, creating parents."""

    def __init__(self, directory: str):
        self._directory = directory

    def write(self, records: List[dict]) -> Path:
        if not records:
            return self._current_path()
        path = self._current_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record) + "\n")
        return path

    def _current_path(self) -> Path:
        today = datetime.now(timezone.utc)
        return CallRecordPath.daily(self._directory, today)


class DayFileUploader:
    """Uploads yesterday's closed JSONL file to Scaleway Object Storage.

    Only the closed day is uploaded: today's file is still being written, so
    uploading it would produce a partial object that a reduce step could
    mistake for the full day. boto3 is imported lazily — the store works
    without it when no credentials are configured.
    """

    def __init__(self, bucket: str, directory: str, client: Any = None):
        self._bucket = bucket
        self._directory = directory
        self._client = client

    @classmethod
    def from_environment(cls, bucket: str, directory: str) -> Optional["DayFileUploader"]:
        access_key = os.getenv(EnvKey.SCW_ACCESS_KEY.value)
        secret_key = os.getenv(EnvKey.SCW_SECRET_KEY.value)
        if not access_key or not secret_key:
            logger.info(
                "%s/%s not set — [call] records are written to disk but not uploaded",
                EnvKey.SCW_ACCESS_KEY.value,
                EnvKey.SCW_SECRET_KEY.value,
            )
            return None
        import boto3  # noqa: PLC0415  (lazy: only needed when uploading; the
        # ruff import rule is off for exactly this documented-exception case)

        client = boto3.client(
            "s3",
            endpoint_url=os.getenv(EnvKey.SCW_ENDPOINT_URL.value, "https://s3.fr-par.scw.cloud"),
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=os.getenv(EnvKey.SCW_REGION.value, "fr-par"),
        )
        return cls(bucket, directory, client)

    def upload_previous_day(self) -> None:
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        path = CallRecordPath.daily(self._directory, yesterday)
        if not path.exists():
            return
        key = path.name
        try:
            self._client.upload_file(str(path), self._bucket, key)
        except Exception:
            # Never raise: persistence is best-effort. The file stays on disk
            # and the next pass retries it.
            logger.exception("Failed to upload %s; will retry on next flush", key)


class CallRecordStore:
    """The single entry point: buffers records, flushes to disk, uploads.

    One instance per process, created in ``configure()`` at startup (before
    gunicorn forks, so the flusher thread survives) and read by
    :meth:`CallRecorder.__exit__` via :meth:`record`. When no bucket is
    configured the store is simply absent — records go to stdout only.
    """

    _instance: Optional["CallRecordStore"] = None

    def __init__(self, directory: str, bucket: Optional[str], flush_seconds: int):
        self._buffer = CallRecordBuffer()
        self._writer = DayFileWriter(directory)
        self._uploader = (
            DayFileUploader.from_environment(bucket, directory) if bucket else None
        )
        self._flush_seconds = flush_seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # -- lifecycle -----------------------------------------------------------

    @classmethod
    def configure(cls) -> None:
        """Build the store from the environment, if a bucket is configured."""
        bucket = os.getenv(EnvKey.CALL_RECORDS_BUCKET.value, "").strip()
        if not bucket:
            logger.info(
                "%s not set — [call] records go to stdout only",
                EnvKey.CALL_RECORDS_BUCKET.value,
            )
            cls._instance = None
            return
        directory = os.getenv(EnvKey.CALL_RECORDS_DIR.value, CallRecordPath.DEFAULT_DIR)
        try:
            flush_seconds = int(os.getenv(EnvKey.CALL_RECORDS_FLUSH_SECONDS.value, "30"))
        except ValueError:
            logger.warning("Invalid %s value; falling back to 30s",
                           EnvKey.CALL_RECORDS_FLUSH_SECONDS.value)
            flush_seconds = 30
        cls._instance = cls(directory, bucket, max(1, flush_seconds))
        cls._instance.start()

    @classmethod
    def record(cls, record: dict) -> None:
        """Append one record to the store, if one is configured."""
        if cls._instance is not None:
            cls._instance._buffer.append(record)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="call-record-store")
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self._flush_seconds):
            self.flush()

    def flush(self) -> None:
        """Write buffered records to the day file and upload the closed day."""
        drained = self._buffer.drain()
        try:
            self._writer.write(drained)
        except OSError:
            # The drain is already done — put the records back so the next
            # flush retries them, and never lose data to a full disk silently.
            logger.exception("Failed to write [call] records; retrying next flush")
            for record in drained:
                self._buffer.append(record)
            return
        if self._uploader is not None:
            self._uploader.upload_previous_day()