"""Unit tests for StageTimer."""

import logging

import pytest

from src.server.services.helpers.timing import StageTimer

logger = logging.getLogger("logger")


def test_logs_stage_with_timing_prefix_and_ms(caplog):
    with caplog.at_level(logging.INFO, logger="logger"):
        with StageTimer("my_stage", logger):
            pass
    assert any("[timing] my_stage:" in r.message and r.message.endswith("ms")
               for r in caplog.records)


def test_logs_on_exception_and_does_not_suppress(caplog):
    with caplog.at_level(logging.INFO, logger="logger"):
        with pytest.raises(ValueError):
            with StageTimer("boom", logger):
                raise ValueError("x")
    # Timing is logged even when the block raised (logged on __exit__).
    assert any("[timing] boom:" in r.message for r in caplog.records)
