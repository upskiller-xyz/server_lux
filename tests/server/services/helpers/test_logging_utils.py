from src.server.services.helpers.logging_utils import (
    LengthReplacementStrategy,
    LoggingDictFormatter,
)


def test_trimmed_mesh_is_summarized_with_rounded_first_value():
    payload = {"mesh": [[1.23456, 2.34567], [3.45678, 4.56789]]}

    result = LoggingDictFormatter().format(payload)

    assert result == {"mesh": "<list of 2 items, first=1.23>"}


def test_trimmed_coordinate_payload_does_not_call_recursive_rounding(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("recursive rounding should not run for trimmed payloads")

    monkeypatch.setattr(
        LengthReplacementStrategy,
        "_round_nested_floats",
        fail_if_called,
    )

    result = LoggingDictFormatter().format({"mesh": [[1.23456, 2.34567]]})

    assert result == {"mesh": "<list of 1 items, first=1.23>"}
