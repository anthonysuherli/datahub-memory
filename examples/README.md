# Sample outputs (canonical run)

Everything under `examples/` is pulled verbatim from the canonical run behind `demo/counters-baseline.json` (2026-07-28, live against docker-quickstart DataHub v1.5.0.6 + `mcp-server-datahub` v0.6.0). Sources: the canonical run's own `.data/delapan.db` (unmodified since that run) and the build log that produced `demo/counters-baseline.json` (internal, not published). No text has been reworded.

- [`investigation-answer.md`](investigation-answer.md) — the agent's own answers for beat 1 (fresh investigation) and beat 3 (drift → re-verify), plus the full finding content persisted for each.
- [`resolution-log.md`](resolution-log.md) — the `resolution_events` table excerpt and per-beat ops-delta (ADD/UPDATE/NOOP) that the resolver produced.
- [`verify-only-output.md`](verify-only-output.md) — `demo/run_demo.sh --verify-only`'s output re-checking the beat-3 bi-temporal-retirement gate against the current DB, no live run required.
