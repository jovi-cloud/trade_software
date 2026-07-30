"""Explain event serialization tests."""

from __future__ import annotations

from app.domain.reason_codes import ReasonCode
from app.engine.explain.serialize import event_from_dict, event_to_dict


def _legacy_event() -> dict[str, object]:
    return {
        "seq": 1,
        "event_type": "run_started",
        "layer": "system",
        "timestamp_ms": 1_000,
        "bar_index": None,
        "reason_code": "lifecycle.run_started",
        "status": "info",
        "order_id": None,
        "trade_seq": None,
        "message": "Run started",
    }


def test_event_from_dict_normalizes_legacy_reason_codes() -> None:
    event = event_from_dict(_legacy_event())
    assert event.reason_code == ReasonCode.SYSTEM_RUN_STARTED
    assert event.schema_version == 1
    assert event.event_id == "evt-000001"


def test_event_to_dict_includes_trade_id_and_trade_seq() -> None:
    event = event_from_dict(
        {
            **_legacy_event(),
            "trade_id": 2,
            "schema_version": 1,
            "event_id": "evt-000001",
        }
    )
    payload = event_to_dict(event)
    assert payload["trade_id"] == 2
    assert payload["trade_seq"] == 2


def test_event_from_dict_reads_trade_seq_alias() -> None:
    raw = _legacy_event()
    raw["trade_seq"] = 3
    event = event_from_dict(raw)
    assert event.trade_id == 3
