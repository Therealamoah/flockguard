# Daily Farm Brief

## Purpose

Generate a concise, action-oriented daily summary of the whole farm.

## Procedure

1. Retrieve overall farm status (`get_farm_status`) - house count, how
   many are stable, which need attention, missing Morning Checks.
2. Retrieve house comparison (`get_house_comparison`) to identify the
   highest-priority house(s) - combine with the `farm_priority` skill's
   reasoning rather than sorting by Risk Score alone.
3. Retrieve active/unresolved alerts (`get_active_alerts`).
4. Retrieve trend insights across houses (`get_trend_insights` per house,
   or the farm-level trend summary if already available).
5. Retrieve unresolved priorities - alerts with no completed inspection
   yet (`get_unresolved_priorities`).
6. Determine the farm's top 1-3 priorities for today.
7. Generate a short, warm, action-oriented brief: overall condition
   first, then the specific reason the top priority needs attention, then
   a short list of what the farmer should do today.

## Notes

The deterministic version of this brief (house counts, missing checks,
critical alert count) is computed by `app/services/daily_brief_service.py`
without any AI involvement, and is always available even if this skill's
AI-generated version is not. Do not regenerate this brief on every page
load - it should be cached/reused for the farm/day where practical (see
`app/api/routes/ask.py`'s daily-brief caching).
