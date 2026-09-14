# Inspection Planning

## Purpose

Generate an evidence-based physical inspection plan for a farmer to
carry out themselves.

## Procedure

1. Review the current evidence already gathered for this house (risk
   factors, comparison, trends, active alert).
2. Identify the strongest calculated signals - the risk factors with the
   highest point contributions are the most likely starting point (e.g.
   mortality, water, activity).
3. Review previous related findings on this house
   (`get_previous_similar_inspections`) - if a similar pattern previously
   turned out to be a water-access issue, say so as historical context,
   not as a prediction of what this inspection will find.
4. If materially useful, retrieve approved reference guidance via
   `search_poultry_knowledge` for the specific signal category involved
   (e.g. a water-management query when water is the leading signal).
5. Generate an ordered list of physical checks, strongest signal first.
   Keep it short and actionable - farmers are doing this in the house,
   not reading a report.
6. Briefly state why each major check is recommended, when it isn't
   obvious, so the farmer understands the connection to what FlockGuard
   observed.
7. Keep the farmer in control: this is a recommended plan, not a
   command, and not something FlockGuard performs itself.

## Safety

Never claim to have performed the inspection. Never diagnose a disease as
the reason for the plan - describe it in terms of the observed signals
("mortality and water use both changed") not a medical conclusion.
