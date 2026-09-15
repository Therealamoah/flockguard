"""Shared notification-preference defaults and gating logic - used by both
app/api/routes/settings.py (GET/PATCH /settings, what the farmer sees and
edits) and app/api/routes/flock_checks.py (deciding whether a brand-new
alert actually sends an email), so the two can never drift out of sync
about what "email notifications are on" means.
"""

DEFAULT_NOTIFICATION_PREFERENCES = {
    "critical_alerts": True,
    "warning_alerts": True,
    "watch_alerts": False,
    "morning_check_reminder": True,
    "evening_check_reminder": True,
    "daily_farm_brief": True,
    # in_app, email and push are real (all opt-in except in_app); whatsapp/sms
    # are permanently "coming_soon" - never advertise a channel as working
    # before it actually sends something.
    "channels": {"in_app": True, "push": False, "email": False, "whatsapp": "coming_soon", "sms": "coming_soon"},
}


def get_notification_preferences(farm: dict) -> dict:
    """Merges a farm's stored preferences over the defaults - a farm
    created before this feature existed simply lacks the field and gets
    the defaults untouched, matching
    app/api/routes/settings.py::get_settings's own DEFAULT_SETTINGS merge.
    """
    stored = farm.get("notification_preferences") or {}
    channels = {**DEFAULT_NOTIFICATION_PREFERENCES["channels"], **stored.get("channels", {})}
    return {**DEFAULT_NOTIFICATION_PREFERENCES, **stored, "channels": channels}


def _channel_enabled_for_status(farm: dict, status: str, channel: str) -> bool:
    """Shared gate for every per-channel alert-delivery check: the channel
    itself AND that severity's own toggle must both be on. `status` is one
    of watch/warning/critical (see
    app/services/alert_engine.py::ALERT_WORTHY_STATUSES) - each has its own
    toggle since a farmer may want critical alerts delivered but not
    routine watch-level ones (watch_alerts defaults to False for exactly
    this reason)."""
    prefs = get_notification_preferences(farm)
    if not prefs["channels"].get(channel):
        return False
    return bool(prefs.get(f"{status}_alerts", True))


def alert_email_enabled(farm: dict, status: str) -> bool:
    """Whether a newly-opened alert of this status should actually email
    the org's owners/managers."""
    return _channel_enabled_for_status(farm, status, "email")


def push_enabled(farm: dict, status: str) -> bool:
    """Whether a newly-opened alert of this status should actually push
    (FCM web push) to the org's owners/managers - see
    app/services/push_service.py for the send side."""
    return _channel_enabled_for_status(farm, status, "push")
