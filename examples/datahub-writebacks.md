# Write-backs: what the agent put *into* DataHub

The other files in `examples/` show what the agent concluded and how the resolver
recorded it. This one shows the artifacts the agent **wrote back into the catalog**
— the part of the loop that makes the next person inherit the answer instead of
re-deriving it, via `mcp-server-datahub`'s own mutation tools (`save_document`,
`update_description`).

**Provenance.** Everything below was read back out of the live docker-quickstart
DataHub instance (v1.5.0.6) *after* the run, verbatim, via GMS aspect reads
(`GET /aspects/{urn}?aspect=…&version=N`) — not from an agent transcript. Nothing
has been reworded or reformatted.

Note these come from the **video-recording run of 2026-07-29 (EDT)**, not the
2026-07-28 canonical run behind `demo/counters-baseline.json` that the other
`examples/` files quote. That is deliberate: these are the exact artifacts you
watch land in the [demo video](https://youtu.be/d-R0-WuPzXw), so you can read in
full what the video only shows on screen. DataHub's aspect versioning preserved
both the beat-1 and beat-3 states, so each artifact is shown before and after.

The two `created` timestamps below (03:11:24Z and 03:37:23Z = 23:11 and 23:37 EDT)
match the terminal clock visible in the video's left pane during beat 1 and beat 3.

---

## Artifact 1 — an agent-authored DataHub Document

Written with `save_document`, and attached to all four datasets in the chain, so it
surfaces from any of them:

- **URN:** `urn:li:document:shared-ed933c9a-849d-4880-9c86-bd75b60a12dc`
- **Title:** `Trust review 2026-07-29: monthly_revenue for the board report`
- **Related assets:** `monthly_revenue`, `fct_revenue`, `stg_payments`, `raw_payments`

### 1a. As beat 1 wrote it (aspect version 1, created 2026-07-30T03:11:24Z)

2196 characters. The first investigation: one caveat, and two documentation
gaps flagged as non-blocking.

````markdown
## Verdict

**Trusted, with one caveat** — usable for the board report provided the figures are pulled on or after **2026-07-26**.

## What was checked

Upstream lineage walked to the root, and institutional memory read on **every** entity in the chain, not just the dataset asked about:

```
raw_payments (root)  ->  stg_payments  ->  fct_revenue  ->  monthly_revenue
per payment, cents      per payment, USD    daily, USD      monthly, USD
```

- Single linear 3-hop path, no branches or alternate sources — any upstream problem reaches the board number undiluted.
- DataHub incident health: `PASS` on all four datasets.
- `monthly_revenue` is explicitly documented as the "monthly revenue rollup used by the board dashboard" (`month`, `revenue_usd`).

## The caveat

The only incident in the chain is recorded on the **root source `raw_payments`**, not on `monthly_revenue`:

> **INCIDENT 2026-07-24: Stripe webhook outage — late backfill.** Stripe webhook delivery was down ~6 hours on 2026-07-24. Payment events landed late in `raw_payments`, so `stg_payments`, `fct_revenue`, and `monthly_revenue` all carried an incomplete Jul 24 slice. The missed events were backfilled and the chain recomputed on **2026-07-26**; Jul 24 figures are now correct.

**Action:** treat any July export taken before 2026-07-26 as stale — it understates the Jul 24 slice, and therefore the July total. Re-pull.

## Documentation gaps found (not blocking)

1. `stg_payments` had an **empty description** — the one hop where the cents→dollars conversion (`amount_cents` → `amount_usd`) happens was undocumented. Filled as part of this review.
2. **No SQL captured** anywhere in the chain (`get_dataset_queries` on `monthly_revenue` returns 0), so the daily→monthly aggregation logic is not inspectable in the catalog.

Net: the number is trusted on the strength of lineage plus the incident record, not on documented transformation logic.

## Grounded in

- `urn:li:dataset:(urn:li:dataPlatform:demo,monthly_revenue,PROD)`
- `urn:li:dataset:(urn:li:dataPlatform:demo,fct_revenue,PROD)`
- `urn:li:dataset:(urn:li:dataPlatform:demo,stg_payments,PROD)`
- `urn:li:dataset:(urn:li:dataPlatform:demo,raw_payments,PROD)`
````

### 1b. As beat 3 rewrote it after the drift (aspect version 0, created 2026-07-30T03:37:23Z)

3463 characters. Same URN — `save_document` upserts, so the catalog carries one
current trust review rather than an append-only pile. The verdict is downgraded, a
second caveat is added, and the earlier "documentation gap" is re-framed as an active
correctness risk.

````markdown
## Verdict

**Trusted with caveats — and there are now TWO, not one.** Superseded the earlier single-caveat verdict after a re-verification on 2026-07-29 detected undocumented schema drift.

Do not put the figure in front of the board until caveat 2 is cleared.

## What was checked

Upstream lineage walked to the root and institutional memory read on **every** entity in the chain, then every entity's schema + lineage re-hashed against the previously recorded state:

```
raw_payments (root)  ->  stg_payments  ->  fct_revenue  ->  monthly_revenue
per payment, cents      per payment, ???    daily, USD      monthly, USD
```

- Single linear 3-hop path, no branches or alternate sources — any upstream problem reaches the board number undiluted. **Topology unchanged.**
- Deterministic freshness check over all 4 entities: **1 of 4 drifted — `stg_payments`.** `monthly_revenue`, `fct_revenue`, `raw_payments` unchanged.
- DataHub incident health: `PASS` on all four datasets. **It did not catch the drift** — health status is not a substitute for hash-based drift detection.

## Caveat 1 — Jul 24 webhook outage (unchanged, resolved)

Recorded on the **root source `raw_payments`**, not on `monthly_revenue`:

> **INCIDENT 2026-07-24: Stripe webhook outage — late backfill.** Stripe webhook delivery was down ~6 hours on 2026-07-24. Payment events landed late in `raw_payments`, so `stg_payments`, `fct_revenue`, and `monthly_revenue` all carried an incomplete Jul 24 slice. Missed events were backfilled and the chain recomputed on **2026-07-26**; Jul 24 figures are correct as of then.

**Action:** treat any July export taken before 2026-07-26 as stale — it understates the Jul 24 slice and therefore the July total. Re-pull.

## Caveat 2 — NEW: undocumented column rename on stg_payments

`stg_payments.amount_usd` is now **`amount`**. Current schema: `payment_id` (string), `paid_date` (string), `amount` (number).

Nothing in the catalog records this rename — no incident, no document, no description update. Why it matters:

1. **The unit assertion was erased.** `amount_usd` named its unit; `amount` does not. `stg_payments` is the single hop where `raw_payments.amount_cents / 100` is supposed to happen.
2. **The description had gone stale into being wrong.** It still described `amount_usd`, so the only prose documenting the divide-by-100 cited a column that no longer exists. A wrong description is a worse failure mode than an empty one, because it reads as verification. Corrected as part of this review.
3. **Unverifiable from the catalog.** `get_dataset_queries` returns **0** for `stg_payments`, `fct_revenue` and `monthly_revenue`, so neither the unit conversion nor the daily→monthly rollup is inspectable as SQL.

**Risk:** if the rename accompanied a units change, `monthly_revenue.revenue_usd` would be inflated ~100x and nothing in DataHub would say so.

**Action before the board report:**
- Confirm against the warehouse transform that `stg_payments.amount` is still dollars.
- Sanity-check the monthly total against a known-good prior month.
- Durable fix: capture the transform SQL into DataHub so unit semantics survive column renames.

## Grounded in

- `urn:li:dataset:(urn:li:dataPlatform:demo,monthly_revenue,PROD)`
- `urn:li:dataset:(urn:li:dataPlatform:demo,fct_revenue,PROD)`
- `urn:li:dataset:(urn:li:dataPlatform:demo,stg_payments,PROD)` — the drifted entity
- `urn:li:dataset:(urn:li:dataPlatform:demo,raw_payments,PROD)`
````

**What changed, and why it is the point.** Beat 1 reported `stg_payments` as
`per payment, USD`. Beat 3 reports it as `per payment, ???` — because `amount_usd`
became `amount` and the unit assertion was erased. The agent did not merely notice a
hash change; it worked out that the *stale description had become actively wrong*,
and said so in the artifact: "A wrong description is a worse failure mode than an
empty one, because it reads as verification."

---

## Artifact 2 — the dataset description on `stg_payments`

Written with `update_description`. `demo/seed.py` seeds this description **empty** on
purpose ([`seed.py`](../demo/seed.py), `DESCRIPTIONS["stg_payments"] = ""`), so
everything below is agent-authored.

### 2a. Beat 1 fills the empty description (aspect version 19)

593 characters. This is the text that appears in the DataHub pane at **0:50** in
the video, while `Skill(datahub-memory:writeback)` is on screen in the terminal.

```markdown
Staged one-row-per-payment table sitting between `raw_payments` and `fct_revenue`. Normalizes the raw Stripe events: `amount_cents` is converted to dollars as `amount_usd` (cents / 100) and the `paid_at` event timestamp is truncated to a `paid_date` day key; `payment_id` carries through as the grain. This is the hop where the revenue chain's unit conversion happens, so a units bug here propagates unchanged to `fct_revenue` and `monthly_revenue` (the board dashboard number). Affected by the 2026-07-24 Stripe webhook outage — see the incident note on `raw_payments`; recomputed 2026-07-26.
```

### 2b. Beat 3 corrects it after the rename (aspect version 0 — current)

1331 characters. This is the text that appears at **2:00** in the video.

```markdown
Staged one-row-per-payment table sitting between `raw_payments` and `fct_revenue`. Grain is `payment_id`; the `paid_at` event timestamp from the raw Stripe events is truncated to a `paid_date` day key.

**⚠️ Column renamed, units now unasserted (detected 2026-07-29).** The amount column is currently named **`amount`**. It was previously `amount_usd`, and the rename is undocumented — no incident, no changelog, and DataHub incident health stayed `PASS` throughout. This is the one hop in the revenue chain where the cents→dollars conversion (`raw_payments.amount_cents` / 100) is supposed to happen, and the old column name was the only place in the catalog that asserted the unit. `amount` asserts nothing.

Downstream `fct_revenue.revenue_usd` and `monthly_revenue.revenue_usd` (the board dashboard number) still claim USD, so the conversion must still occur here — but **no SQL is captured for this dataset** (`get_dataset_queries` returns 0), so that cannot be verified from DataHub. If the rename accompanied a units change, the board figure would be inflated ~100x with nothing in the catalog to flag it. Verify against the warehouse transform before trusting downstream revenue figures.

Also affected by the 2026-07-24 Stripe webhook outage — see the incident note on `raw_payments`; backfilled and recomputed 2026-07-26.
```

---

## Not agent output

`urn:li:document:shared-77664d7f-0189-43f0-92cc-11e5d2319b3f` — "INCIDENT 2026-07-24:
Stripe webhook outage — late backfill" — is **seed data**, published by
`demo/seed.py`, not written by the agent. It is the incident the investigation is
supposed to find four hops upstream. It is listed here only so it is not mistaken
for a generated artifact.
