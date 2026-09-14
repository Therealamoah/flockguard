# Investigate Flock Risk

## Purpose

Investigate why a poultry house may require attention, using FlockGuard's
own real data - never a guess.

## When to use this skill

- A Flock Check came back Watch, Warning, or Critical.
- Risk changed significantly since the previous check.
- A farmer asks "why is House X flagged?" or similar.

## Procedure

1. Retrieve the house's latest Flock Check (`get_latest_flock_check`).
2. Retrieve the Morning/Evening comparison for today, if available
   (`get_morning_check`, `get_evening_check`, or the check's own
   `morning_comparison` field).
3. Retrieve recent mortality history (`get_mortality_history`).
4. Retrieve recent feed history (`get_feed_history`).
5. Retrieve recent water history (`get_water_history`).
6. Review activity/behaviour changes recorded on the latest check.
7. Review the deterministic risk score and risk change
   (`get_risk_history`) - these are already calculated; never recompute
   or override them.
8. Review active alerts for this house (`get_active_alerts`).
9. Review recent inspections for this house (`get_recent_inspections`).
10. Review previous similar incidents on this house/flock
    (`get_previous_similar_inspections`), if a finding category is
    relevant.
11. Decide whether approved external poultry-management guidance would
    materially improve the investigation (e.g. the evidence points at
    water, feed, ventilation, or a behaviour pattern where general
    guidance helps). If the evidence is purely about numbers already
    explained by the Risk Engine's own factors, reference knowledge
    usually adds nothing - skip it.
12. If step 11 says yes, call `search_poultry_knowledge` with a specific,
    targeted query (not the whole case). Only cite a source you actually
    received back from that call.
13. Determine operational priority (see the `farm_priority` skill for how
    priority differs from the raw Risk Score).
14. Produce an evidence-backed explanation, citing which category each
    piece of evidence belongs to (see `poultry_safety`).
15. If the situation warrants a physical check, generate an inspection
    plan (see the `inspection_planning` skill) and set
    `requires_inspection: true`.

## Safety

Follow the `poultry_safety` skill in full. In particular: never diagnose
disease, never prescribe medication, never invent missing measurements,
never let reference knowledge substitute for a missing farm record.
