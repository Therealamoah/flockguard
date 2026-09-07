NORMAL = "normal"
WATCH = "watch"
WARNING = "warning"
CRITICAL = "critical"

# Matches the FlockGuard-wide risk system: score is always paired with
# color + icon + status text in the UI, never color alone.
_THRESHOLDS = (
    (24, NORMAL),
    (49, WATCH),
    (74, WARNING),
    (100, CRITICAL),
)


def classify_status(score: int) -> str:
    for ceiling, status in _THRESHOLDS:
        if score <= ceiling:
            return status
    return CRITICAL
