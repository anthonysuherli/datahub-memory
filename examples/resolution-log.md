# resolution-log excerpt (resolution_events / ops-delta)

Captured from the canonical run behind `demo/counters-baseline.json` (2026-07-28, live against
docker-quickstart DataHub v1.5.0.6 + `mcp-server-datahub` v0.6.0).

The runner's per-beat deltas are the canonical resolver counts. `before` and `after` are
`select op, count(*) from resolution_events group by op` snapshots:

```
--- resolution_events delta after beat 1 ---
  ADD: +3
  NOOP: +1

--- resolution_events delta after beat 2 ---
  (no new resolution_events)

--- resolution_events delta after beat 3 (re-verify) ---
  ADD: +2
  UPDATE: +1
```

The beat-3 `UPDATE` row's full detail, queried directly:

```
op      target    new       reason
UPDATE  75a5ab8b  aabef4d1  This is a re-verification of the same trust question about
                            monthly_revenue for the board report...
```

`target_finding_id=75a5ab8b` is beat 1's original trust-verdict finding; `new_finding_id=aabef4d1` is the re-verified one (see `examples/investigation-answer.md`). `75a5ab8b`'s `invalidated_at` is now `2026-07-28T05:42:26.466117+00:00` — retired, not deleted.
