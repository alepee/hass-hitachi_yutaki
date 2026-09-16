# Fleet refrigerant analysis

Offline analysis pipeline over the telemetry archive (R2 bucket
`hitachi-telemetry-archive`) that builds **per-model refrigerant operating
profiles** (`Tg−Te`, `EVO`) and stress-tests the
[`RefrigerantMonitor`](../../custom_components/hitachi_yutaki/domain/services/refrigerant.py)
detector (issue [#310](https://github.com/alepee/hass-hitachi_yutaki/issues/310))
against real fleet behaviour.

First run: 2026-07-22, on 24 days sampled Apr–Jul 2026 (~1.1 M
compressor-running points, 46 eligible installations). Key findings feeding
detector iteration 2:

- `compressor_tg_gas_temp` is the **THMg gas-pipe thermistor** (register 1206),
  not the suction line: `Tg−Te` is a lift-like signal, typically **40–60 K in
  heating**, not a 2–8 K suction superheat.
- The detector's `SUPERHEAT_MAX_K = 40` plausibility cap therefore rejects most
  qualifying heating points on several models (80–90 % on S80, ~98 % on M).
- Inter-instance spread within a model reaches 26 K → absolute thresholds are
  impossible; the per-installation learned baseline is the right design, and
  the per-model bands serve as data-quality sanity checks.
- In cooling the signal flips sign and EVO pins at 100 %: the detector's
  heating-only sampling gate is confirmed correct.

> **Privacy**: everything under `data/` is gitignored and must stay out of the
> repo. Do not republish fleet-wide aggregate counts (instances, per-model
> totals) in public artifacts (issues, PRs, release notes). See
> [docs/development/telemetry-dataset.md](../../docs/development/telemetry-dataset.md).

## Prerequisites

- `duckdb` (CLI) and `python3` (stdlib only).
- R2 S3 read credentials in `backend/.env.r2` (gitignored, never committed):

  ```bash
  R2_KEY_ID=...
  R2_SECRET=...
  ```

  Create them in the Cloudflare dashboard → R2 → *Manage R2 API Tokens* →
  read-only token scoped to `hitachi-telemetry-archive`.

## Pipeline

```bash
./pull_installations.sh                     # 1. hash → profile map
./pull_day.sh 2026-04-02 2026-04-07 ...     # 2. one CSV per fleet-day (~1-2 min each)
python3 analyze.py                          # 3. per-instance profiles + summary table
python3 build_model_profiles.py             # 4. per-model roll-up (chart-ready JSON)
python3 fp_simulation.py                    # 5. false-positive pressure estimate
```

1. **`pull_installations.sh`** → `data/installations.json`. Maps the 12-char
   instance hash to its installation payload (profile, capabilities).
2. **`pull_day.sh YYYY-MM-DD ...`** → `data/days/<day>.csv`. Extracts
   compressor-running points (defrost excluded) with the refrigerant-relevant
   fields: `tg`, `te`, `evo`, `outdoor`, `freq`, `op_state`. Already-downloaded
   days are skipped, so it is resumable and incremental.
3. **`analyze.py`** → `data/profiles_per_instance.json`. Applies the same
   qualifying filters as the `RefrigerantMonitor` (frequency band, plausibility
   ranges — except the 40 K cap, see module docstring), segments by operation
   mode (`heat` / `dhw` / `cool` / `pool`), aggregates per instance-day
   (medians, ≥30 samples/day) then per instance, and excludes instances with a
   phantom `Tg` (register stuck at 0).
4. **`build_model_profiles.py`** → `data/profiles_per_model.json`. Fleet bands
   per model × mode and SH/EVO vs outdoor-temperature curves (2 °C bins).
5. **`fp_simulation.py`** replays the detector's decision rule (baseline →
   sliding recent window → watch/alert thresholds, EVO temp-matched
   corroboration) on the collected daily aggregates of the presumed-healthy
   fleet: any alert condition is a false positive. Compares the as-shipped
   40 K cap against the proposed 80 K cap. **Needs consecutive heating-season
   days** to be meaningful — sample a full month of the heating season, not
   1 day in 5.

## One-off maintenance

- **`backfill_snapshot_time.py`**: rewrites the archived snapshots that have
  no `time` in their body (everything ingested before the Worker fix for
  #442), reconstructing it from the ingestion epoch in the object name and
  tagging it `time_source: "backfill"`. Dry run by default, `--apply` to
  write; idempotent, so safe to re-run. Needs a **write** R2 token, unlike the
  rest of this directory. Deploy the Worker first, then run it.

## Sampling guidance

- A fleet-day is ~12 k batch files; `pull_day.sh` takes ~1-2 min per day.
- For **seasonal profiles** (steps 3-4), sparse sampling is fine (e.g. every
  5th day across months).
- For **detector replay** (step 5), pull consecutive days of the heating
  season (e.g. all of January) so the 14-day baseline + 7-day windows match
  the real detector dynamics.

## Known gaps (as of 2026-07)

- The archive starts in April 2026: **no winter data yet**. There are zero
  points below 0 °C outdoor; EVO curves and the "superheat is season-robust"
  assumption must be re-validated on winter 2026-27 data (re-run steps 2-5 on
  Jan–Feb 2027 days).
- Metric points only carry what the integration version of each reporter
  collects: older instances may lack `evo`/`op_state` and drop out of the
  filters.
