# `demo/run_demo.sh --verify-only` output

Captured verbatim from a separate successful run of the same three-beat scenario. Resolver ADD
counts can vary with model classification; the gate's invariant is an `UPDATE` or `SUPERSEDE` event
plus an increase in retired findings. The canonical timing and tool-call metrics remain
[`demo/counters-baseline.json`](../demo/counters-baseline.json).

This command made no live agent call and no DataHub round trip; it queried the local SQLite database
and snapshots left by the preceding full run:

```
== --verify-only: exercising the beat-3 gate against the CURRENT DB, no beats run ==
--- resolution_events delta after beat 3 (re-verify) ---
  ADD: +1
  UPDATE: +1
--- retired findings: before=0 after=1 (delta=+1) ---
stale finding retired bi-temporally (op: UPDATE -- resolver classified refinement; SUPERSEDE fires on outright contradictions)
=== bi-temporal check: findings (live vs retired) ===
title                                                         status
------------------------------------------------------------  -------
Can I trust monthly_revenue for the board report?             retired
What incident affected monthly_revenue?                       live
What is the lineage of monthly_revenue?                       live
What is monthly_revenue used for?                             live
Re-verification 2026-07-28: Has stg_payments schema changed?  live
Can I trust monthly_revenue for the board report as of 2026-  live
=== retired_findings count ===
1
```

Exit code `0`. The historical command output above uses the runner's original “bi-temporal” label;
the implemented guarantee is more precisely **versioned soft retirement**. The gate requires both
(a) an `UPDATE` or `SUPERSEDE` event since the pre-beat-3 snapshot and (b) an increase in rows whose
`findings.invalidated_at` is set. It aborts non-zero if either condition fails.
