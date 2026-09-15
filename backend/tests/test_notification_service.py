from app.services.notification_service import (
    DEFAULT_NOTIFICATION_PREFERENCES,
    alert_email_enabled,
    get_notification_preferences,
    push_enabled,
)


def test_defaults_apply_to_a_farm_that_predates_this_feature():
    prefs = get_notification_preferences({})
    assert prefs == DEFAULT_NOTIFICATION_PREFERENCES


def test_stored_preferences_merge_over_defaults_not_replace_them():
    farm = {"notification_preferences": {"watch_alerts": True, "channels": {"email": True}}}
    prefs = get_notification_preferences(farm)
    assert prefs["watch_alerts"] is True  # overridden
    assert prefs["critical_alerts"] is True  # untouched default survives
    assert prefs["channels"]["email"] is True  # overridden
    assert prefs["channels"]["in_app"] is True  # untouched default survives


def test_alert_email_disabled_by_default_even_for_critical():
    # channels.email defaults to False - opt-in, never spam by default.
    assert alert_email_enabled({}, "critical") is False


def test_alert_email_requires_both_the_channel_and_the_severity_toggle():
    farm_email_only = {"notification_preferences": {"channels": {"email": True}}}
    # watch_alerts defaults to False even with email on - a farmer who
    # wants Critical emails shouldn't be flooded with routine Watch ones.
    assert alert_email_enabled(farm_email_only, "watch") is False
    assert alert_email_enabled(farm_email_only, "critical") is True

    farm_watch_only = {"notification_preferences": {"watch_alerts": True}}
    # severity toggle on but channel off - still no email.
    assert alert_email_enabled(farm_watch_only, "watch") is False


def test_push_disabled_by_default_even_for_critical():
    # channels.push defaults to False - same opt-in rule as email.
    assert push_enabled({}, "critical") is False


def test_push_requires_both_the_channel_and_the_severity_toggle():
    farm_push_only = {"notification_preferences": {"channels": {"push": True}}}
    assert push_enabled(farm_push_only, "watch") is False
    assert push_enabled(farm_push_only, "critical") is True

    farm_watch_only = {"notification_preferences": {"watch_alerts": True}}
    assert push_enabled(farm_watch_only, "watch") is False


def test_email_and_push_toggle_independently():
    # Turning one channel on must never silently enable the other.
    farm_email_only = {"notification_preferences": {"channels": {"email": True}}}
    assert alert_email_enabled(farm_email_only, "critical") is True
    assert push_enabled(farm_email_only, "critical") is False
