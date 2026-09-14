# Flock Monitoring

## Purpose

Understand the current condition and recent change of a specific flock or
house, for questions like "what happened to House A today?" or "what
changed since this morning?"

## Procedure

1. Retrieve the latest Flock Check (`get_latest_flock_check`).
2. Retrieve today's Morning Check and Evening Check if both exist
   (`get_morning_check`, `get_evening_check`).
3. Retrieve the previous check for comparison, if the question is about
   change rather than a single point in time (`get_flock_history` with a
   small limit).
4. Note the risk change (current vs previous risk score) - this is
   already calculated by the Risk Engine; never recompute it yourself.
5. Note mortality change, feed change, water change, and activity change
   between the relevant checks.
6. Check recent trend insights for this house (`get_trend_insights`) -
   these are deterministic pattern detections (e.g. "feed declined 3
   checks running"), not your own inference.
7. Check whether there's an active alert on this house
   (`get_active_alerts`).
8. Only call more tools than the question actually needs. "What happened
   today" does not need three weeks of history; "has mortality increased
   this week" does not need feed or water data.

## Output

Return a concise, farmer-readable summary of the flock's current
condition and what changed, grounded only in what the tools returned.
Do not speculate about causes beyond what the data and any active alert
already indicate.
