# `demo/run_demo.sh --verify-only` output

Pulled verbatim from the canonical run behind `demo/counters-baseline.json` (2026-07-28, live against docker-quickstart DataHub v1.5.0.6 + `mcp-server-datahub` v0.6.0).

Run directly against this repo's current `.data/delapan.db` (the canonical run's own database — no live agent call, no DataHub round trip, pure SQLite queries):

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

Exit code `0`. This is the runner's beat-3 gate — it requires both (a) the `resolution_events` delta since the pre-beat-3 snapshot to contain at least one `UPDATE` or `SUPERSEDE`, and (b) the `findings.invalidated_at` count to have actually increased — and aborts non-zero, naming exactly which ops did fire, if either condition fails.
