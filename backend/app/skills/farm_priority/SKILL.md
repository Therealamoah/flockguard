# Farm Priority

## Purpose

Determine which poultry house deserves the farmer's attention first -
this is a different question from "which house has the highest Risk
Score," and the two can disagree.

## Procedure

1. Retrieve every house's current risk via `get_house_comparison` - this
   gives the deterministic Risk Score per house, already calculated.
2. For each house that isn't clearly Normal/stable, gather additional
   context:
   - Risk change / rate of deterioration (`get_risk_history`).
   - Mortality, feed, and water trend direction (`get_trend_insights`,
     `get_mortality_history`, `get_feed_history`, `get_water_history`).
   - Active alerts and their severity/age (`get_active_alerts`).
   - Whether there's an unresolved priority - an active alert with no
     linked inspection yet (`get_unresolved_priorities`).
   - Recent inspections already completed for that house
     (`get_recent_inspections`) - a house with a recent inspection
     already addressing the issue may need LESS urgency than its raw
     score suggests, not more.
   - Previous similar incidents on that house (`get_previous_similar_inspections`).
3. Weigh these together. A house with a lower Risk Score but rapid
   deterioration, no completed inspection, and a history of a similar
   unresolved issue can reasonably outrank a house with a higher score
   that already has an inspection underway or a stable/improving trend.
4. Never silently overwrite or hide the Risk Score - report it alongside
   your own `priority` field, and explain in `historical_context` or
   `calculated_signals` why priority differs from a simple score ranking
   when it does.
5. Do not rank by numeric Risk Score alone - that defeats the purpose of
   this skill.

## Output

An ordered sense of which house(s) need attention first, each with its
real Risk Score, your `priority` assessment, and a short reason grounded
in the evidence gathered above.
