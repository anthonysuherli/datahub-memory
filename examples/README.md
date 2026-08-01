# Sample outputs

Real artifacts from real runs, so the quality of what this agent produces can be judged without running it. No text anywhere in this folder has been reworded.

## From the canonical run (2026-07-28)

Pulled verbatim from the run behind `demo/counters-baseline.json` (live against docker-quickstart DataHub v1.5.0.6 + `mcp-server-datahub` v0.6.0). Sources: that run's own `.data/delapan.db` (unmodified since) and the build log that produced `demo/counters-baseline.json` (internal, not published).

- [`investigation-answer.md`](investigation-answer.md) — the agent's own answers for beat 1 (fresh investigation) and beat 3 (drift → re-verify), plus the full finding content persisted for each.
- [`resolution-log.md`](resolution-log.md) — the canonical run's per-beat resolver deltas
  (ADD/UPDATE/NOOP) and the stale-to-current finding link.
- [`verify-only-output.md`](verify-only-output.md) — captured output from a separate successful
  `demo/run_demo.sh --verify-only` execution of the version-retirement gate. A fresh clone must run
  the full scenario before `--verify-only` has the required local snapshots.

## From the video-recording run (2026-07-29)

- [`datahub-writebacks.md`](datahub-writebacks.md) — the artifacts the agent wrote **into DataHub**: an authored Document (a trust review attached to all four datasets in the chain) and the `stg_payments` description, each shown as beat 1 wrote it and as beat 3 corrected it after the schema drift.

These were read back out of the live DataHub instance after the run via GMS aspect reads, not taken from an agent transcript. They come from the run captured in the [demo video](https://youtu.be/d-R0-WuPzXw) rather than the 2026-07-28 canonical run, so you can read in full the artifacts the video only shows landing on screen.
