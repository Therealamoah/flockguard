import json

from app.services.grok_service import _parse_check_fields


def test_parse_keeps_only_valid_mentioned_fields():
    result = _parse_check_fields(
        json.dumps(
            {
                "mortality": 3,
                "sick_or_injured": -1,  # negative - dropped
                "feed_kg": 100,
                "water_level": "lower",
                "activity": "sleepy",  # not an allowed value - dropped
                "unusual_sound_observed": True,
                "humidity_pct": 250,  # out of range - dropped
                "heard": " 3 birds died. ",
            }
        )
    )
    assert result == {
        "mortality": 3,
        "feed_kg": 100,
        "water_level": "lower",
        "unusual_sound_observed": True,
        "heard": "3 birds died.",
    }


def test_parse_rejects_fractional_and_boolean_counts():
    result = _parse_check_fields(json.dumps({"mortality": 2.5, "sick_or_injured": True, "crowding_observed": False}))
    assert result == {"crowding_observed": False, "heard": None}


def test_parse_returns_none_when_nothing_usable():
    assert _parse_check_fields(json.dumps({"heard": "Hello testing"})) is None
