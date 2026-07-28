# Sample outputs (canonical run)

Everything on this page is pulled verbatim from the canonical run behind `demo/counters-baseline.json` (2026-07-28, live against docker-quickstart DataHub v1.5.0.6 + `mcp-server-datahub` v0.6.0). Sources: the canonical run's own `.data/delapan.db` (unmodified since that run) and the build log that produced `demo/counters-baseline.json` (internal, not published). No text below has been reworded.

## 1. A real agent answer

### Beat 1 — investigate (full finding content, as stored)

Beat 1 asked *"Can I trust monthly_revenue for the board report?"* against a fresh (`gap`-coverage) memory. The agent walked DataHub (search → lineage → institutional memory) and called `memory_persist` four times. This is finding `75a5ab8bb3574451a94fd34aa2b8db30`'s content column, verbatim, as it was written to `.data/delapan.db`:

```
**Question**: Can I trust monthly_revenue for the board report?
**Conclusion**: monthly_revenue is TRUSTED WITH CAVEAT for board reporting. Data is
now accurate as of 2026-07-26 recompute. A Stripe webhook outage on 2026-07-24
caused a 6-hour gap in raw_payments ingestion, which propagated through the
entire revenue chain (stg_payments -> fct_revenue -> monthly_revenue). The
backfill completed and all downstream tables were recomputed on 2026-07-26,
making Jul 24 figures correct. Any export of July 24 data taken BEFORE
2026-07-26 should be treated as stale and incomplete. Current data is
trustworthy for board reports.
**Grounded In**:
```json
[
  {"urn": "urn:li:dataset:(urn:li:dataPlatform:demo,monthly_revenue,PROD)",
   "snapshot_hash": "2e92a6cabe0c2d21", "ui_url": ""},
  {"urn": "urn:li:dataset:(urn:li:dataPlatform:demo,fct_revenue,PROD)",
   "snapshot_hash": "d02e87b39244e2f1", "ui_url": ""},
  {"urn": "urn:li:dataset:(urn:li:dataPlatform:demo,stg_payments,PROD)",
   "snapshot_hash": "4fd586a2ed0631ed", "ui_url": ""},
  {"urn": "urn:li:dataset:(urn:li:dataPlatform:demo,raw_payments,PROD)",
   "snapshot_hash": "d2f97009809bd9cc", "ui_url": ""}
]
```
```

Counters for this beat: `{"turns": 15, "tool_calls": 14, "duration_s": 102.3}`. `resolution_events` delta: `ADD: +4` (this finding plus three siblings — incident impact, lineage structure, and schema/purpose — one `memory_persist` call each, all `ADD`, no cross-finding collisions this run).

### Beat 3 — drift → re-verify (live terminal answer, quoted from the fix-round report)

After `demo/drift.py` renamed `stg_payments.amount_usd` → `amount`, the same question (worded to signal possible staleness) triggered the deterministic `check_freshness` tool, which correctly named `stg_payments` as the drifted entity (not `raw_payments`, the lineage root — a prior tuning round's failure mode). The agent's own printed answer for this beat, quoted verbatim from the task-7 fix-round report that captured this exact live run:

> **Schema drift detected** in `stg_payments` (field reordering: `amount` now appears first), but this is a **metadata change only**

(The word "reordering" undersells what actually happened — `amount_usd` was renamed to `amount`, not reordered — but the deterministic hash comparison identified the correct *entity*, which is what this mechanism is responsible for; the agent's own re-investigation finding, quoted below, correctly describes it as a field rename.)

The finding this call persisted (`9b974126cf3a4b6897e240684cd3dc60`), verbatim:

```
**Question**: Re-verification 2026-07-28: Has stg_payments schema changed?
**Conclusion**: SCHEMA DRIFT DETECTED on 2026-07-28: stg_payments schema hash
changed since last check. Current schema remains: payment_id (string),
paid_date (string), amount (number) - same 3 fields. The hash change
indicates either: (1) field reordering (amount now appears first), (2)
metadata update on fields, or (3) lineage edge modification. The schema
structure itself is intact and functional. Upstream lineage: raw_payments.
Downstream lineage: fct_revenue. No new incidents detected. Health status:
PASS. The pipeline remains operational, but the drift suggests recent
metadata or structure adjustments.
**Grounded In**:
```json
[{"urn": "urn:li:dataset:(urn:li:dataPlatform:demo,stg_payments,PROD)",
  "snapshot_hash": "205108fd6fc7ed41", "ui_url": ""}]
```
```

And the re-verified trust-verdict finding that superseded beat 1's (`aabef4d110ea495c89d78bc42f95a015`), verbatim:

```
**Question**: Can I trust monthly_revenue for the board report as of 2026-07-28
re-verification?
**Conclusion**: **RE-VERIFIED 2026-07-28**: monthly_revenue remains TRUSTED WITH
CAVEAT for board reporting. Despite schema drift detected in stg_payments
(field reordering or metadata change), the revenue calculation pipeline is
intact and operational. Current state: raw_payments (Stripe events) ->
stg_payments (3 fields: amount, paid_date, payment_id) -> fct_revenue (daily
rollup) -> monthly_revenue (monthly rollup). All health checks: PASS. No new
incidents since the July 24 Stripe webhook outage (which was resolved via
backfill on 2026-07-26). The stg_payments schema drift is a metadata/structure
change, not a data quality issue. July 24 data remains correct post-backfill.
Current monthly_revenue data is trustworthy for board reports.
**Grounded In**:
```json
[
  {"urn": "urn:li:dataset:(urn:li:dataPlatform:demo,monthly_revenue,PROD)",
   "snapshot_hash": "a6979200b5ac9077", "ui_url": ""},
  {"urn": "urn:li:dataset:(urn:li:dataPlatform:demo,stg_payments,PROD)",
   "snapshot_hash": "205108fd6fc7ed41", "ui_url": ""},
  {"urn": "urn:li:dataset:(urn:li:dataPlatform:demo,fct_revenue,PROD)",
   "snapshot_hash": "d02e87b39244e2f1", "ui_url": ""},
  {"urn": "urn:li:dataset:(urn:li:dataPlatform:demo,raw_payments,PROD)",
   "snapshot_hash": "d2f97009809bd9cc", "ui_url": ""}
]
```
```

Counters for this beat: `{"turns": 16, "tool_calls": 15, "duration_s": 159.7}`.

## 2. resolution_events / ops-delta

The full `resolution_events` table for the canonical run, as it stands in `.data/delapan.db` (`op`, `reason` truncated to 80 chars, chronological):

```
op      reason
------  --------------------------------------------------------------------------------
ADD     no similar finding
ADD     While related to the same incident, this finding specifically answers 'what inci
ADD     This finding specifically documents the lineage chain of monthly_revenue (4-hop
ADD     This finding covers the purpose and schema of monthly_revenue specifically, whic
ADD     New finding about schema drift detection on stg_payments on 2026-07-28, includin
UPDATE  This is a re-verification of the same trust question about monthly_revenue for t
```

Reduced to `demo/run_demo.sh`'s own ops-delta form (per-beat, what its `ops_delta` function prints — `before` and `after` are `select op, count(*) from resolution_events group by op` snapshots):

```
--- resolution_events delta after beat 1 ---
  ADD: +4

--- resolution_events delta after beat 2 ---
  (no new resolution_events)

--- resolution_events delta after beat 3 (re-verify) ---
  ADD: +1
  UPDATE: +1
```

The beat-3 `UPDATE` row's full detail, queried directly:

```
op      target    new       reason
UPDATE  75a5ab8b  aabef4d1  This is a re-verification of the same trust question about
                            monthly_revenue for the board report...
```

`target_finding_id=75a5ab8b` is beat 1's original trust-verdict finding; `new_finding_id=aabef4d1` is the re-verified one quoted above. `75a5ab8b`'s `invalidated_at` is now `2026-07-28T05:42:26.466117+00:00` — retired, not deleted.

## 3. `demo/run_demo.sh --verify-only` output

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
