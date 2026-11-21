# Compressor short-cycling detection

**Status:** beta, opt-in and off by default (`CONF_CYCLING_DETECTION`).
Part of the [preventive maintenance](preventive-maintenance.md) family.

Short cycling is a compressor that starts and stops too often. It wears the compressor,
costs seasonal efficiency, and points at an installation problem rather than a fault in
the machine itself.

> **Advisory.** The detector says *that* the unit cycles. When the unit reports its water
> flow, it also says *why*, with the installation's own numbers (see
> [Per-installation diagnosis](#per-installation-diagnosis)); otherwise it lists the usual
> causes.

## What it measures

On every poll, in **space heating only**, the detector tracks the compressor's
running state and derives, per day:

| Quantity | Meaning |
|---|---|
| **Peak starts** | Highest number of starts within any 60-minute sliding window |
| **Median cycle period** | Median time from one start to the next, in minutes |
| **Median run** | Median duration of a run, in minutes |

A day is **valid** once it holds at least 4 measured cycle periods, and **faulted** when
**both** criteria hold:

```
peak starts >= 6 per 60 min   AND   median cycle period <= 15 min
```

The verdict follows the streak of faulted days:

| Status | Meaning |
|---|---|
| `learning` | No valid day yet |
| `ok` | Valid days, none faulted |
| `watch` | The running day, or a recent one, is faulted |
| `alert` | 3 consecutive faulted days: a repair issue is raised |

The alert clears by itself as soon as a day comes back healthy. There is nothing to
reset, so the repair issue is not fixable: the remedy is an installation change the
integration cannot make.

**Out of season**, the verdict expires: after 14 calendar days without a valid heating
day the streak is dropped and the alert closes. Unlike a refrigerant leak, a cycling
verdict has no actionable meaning in August, and freezing an alert for a whole summer
would only teach users to ignore it. The detector re-earns its verdict in three days
when heating resumes. The `days_since_valid_day` attribute exposes the data age.

## Why not the usual "3 starts per hour"

Because these machines genuinely run short cycles, and the rule of thumb does not survive
contact with the fleet. Replaying the telemetry archive over mid-season heating days:

- median run **6.7 min** (p10 4.6, p90 19.6) against a 10-15 min target;
- median cycle period per unit **26.6 min** (p10 13.3, p75 62.3);
- peak starts per 60 min: p25 2, median 5, p90 7.

Applied to that fleet, a plain `>= 3 starts/h` threshold flags **10 of 14 evaluable units
and raises 8 repair issues, about a third of the parc**. An alert that fires on a third
of installations is worthless.

The conjunction is what makes it usable. Each criterion alone still touches 6 units of
14; together they retain 5 units in `watch` and a **single** installation in `alert`, and
that installation is the worst of the set (9.9 min period, 99 % of its cycles under
30 min, compressor pinned at 31 Hz).

It is not a fatality of the brand either: 6 units out of 17 have a cycle period above
40 minutes. The distribution is wide, and the detector aims at its tail.

## Why there is no learned baseline

Short cycling is a **stable state**, not a drift. The inter-unit over intra-unit
dispersion ratio is **3.3 in heating** (6.4 in cooling): what separates a cycling
installation from a healthy one is what it *is*, not how it *changed*. A learned baseline
would record the fault during its warm-up window and never report it afterwards.

This is the opposite conclusion to the [refrigerant detector](refrigerant-monitoring.md),
and the reason the domain now carries two detection patterns.

## Measurement hygiene

- **Debounce**: a state change must hold for 30 s to count as a transition, so a blip
  does not become a cycle.
- **Data holes**: a poll gap beyond 4 median intervals (floor 90 s) drops the state
  machine instead of inventing a transition across the hole. A lost batch looks exactly
  like a long off period.
- **Defrost**: a defrost stops and restarts the compressor for unrelated reasons, so the
  defrost guard breaks the cycle chain.
- **Regime**: DHW, pool, and cooling cycles are excluded. A heating cycle followed by a
  DHW cycle is not short cycling, and mixing them was the single easiest way to get this
  wrong. Thermo-off and demand-off belong to the heating regime: they are how the
  controller stops the compressor once the water target is reached, or a room thermostat
  ends the demand, so they are the off half of a heating cycle. Treating them as a regime
  change broke the chain at every stop and no period was ever measured (fixed in
  2.2.0-beta.13).
- **First observed state**: the state the detector wakes up in is never counted as a
  start; there is no transition timestamp to measure a period from.

Intra-day measurements are deliberately **not persisted**: a restart mid-day cannot
reconstruct transitions it did not see. Daily aggregates and the alert streak are
persisted in a `Store`.

## Per-installation diagnosis

Since 2.5.0 (#512), the detector also applies a heat balance to each complete heating
cycle (`domain/services/cycling_diagnosis.py`). During a run the loop warms, because the
unit produces more than the emitters absorb; during the rest it cools, because the
emitters alone draw on it. Over a full cycle the loop gives back what it stored, so:

| Quantity | Formula | What it tells |
|---|---|---|
| **Output** `P` | median of `flow x (outlet - inlet) x 1.163` over the run, ramp-up third skipped | What the unit produces while it runs |
| **Absorbed** | `P x run / (run + rest)` | What the emitters actually take |
| **Loop volume** | `P x tau / (c x swing)`, `tau = run x rest / (run + rest)` | The water mass the outlet swing implies, to compare with a buffer requirement |
| **Time at minimum frequency** | share of settled run samples at most 2 Hz above the floor | Whether any modulation margin is left |
| **Return minus target at stop** | `inlet - water target` at the first poll of the rest | Whether the water comes back as hot as it left |
| **Secondary compressor share** (cascade units) | share of settled run samples with the second compressor on, and the median water target then | Whether the cascade engagement drives the cycling |

The frequency floor is the most populated 1 Hz bin of the lower half of the day's
settled run samples: units that cannot modulate further sit on a plateau (31 Hz on many
Yutaki) with ramp samples scattered below it, so a low percentile would land under the
plateau.

Measurement rules:

- only cycles the unit ends itself are measured (**thermo-off**). A room thermostat ending
  the demand (demand-off) does not saturate the loop, so the balance does not apply;
- a cycle is measured when both halves last at least 60 s, the output exceeds 0.5 kW and
  the outlet swing reaches 1 K (the register resolution);
- a defrost, another regime or a data hole discards the cycle in progress, like it breaks
  the cycle chain;
- a day needs at least 4 measured cycles; each quantity is the median over them. The
  installation-level figures are the medians of the last 7 daily medians, preferring the
  faulted days among them, so the advice describes the days that cycled.

The daily diagnosis is persisted with the day's aggregate. It is exposed as attributes of
`sensor.*_compressor_cycling` (`output_kw`, `absorbed_kw`, `load_ratio_pct`,
`loop_volume_l`, `cycle_run_min`, `cycle_rest_min`, `water_swing_k`,
`time_at_min_frequency_pct`, `return_minus_target_at_stop_k`,
`secondary_compressor_share_pct`, `secondary_compressor_water_target_c`,
`diagnosis_days`, `diagnosed_cycles`), and fills the repair issue: with a measured heat
balance the issue quotes the unit's output, absorbed heat, loop volume and cycle lengths
instead of the generic list of causes. On a cascade unit (S80) whose secondary compressor
runs at least 20% of the settled run time, it adds the water target at which it runs:
the secondary compressor raises the minimum output and shortens the runs further, so a
heating curve that keeps the water target below that level in mild weather lengthens
them.

**Validation.** `backend/analysis/replay_cycling_diagnosis.py` replays the telemetry
archive through the integration's own `CyclingMonitor` (no second implementation). On
five days of late-October 2026 data it reproduces an earlier standalone feasibility
study and gives:

- volumes between ~16 and ~160 L on units without a buffer, stable from one day to the
  next on a given unit (for example 73-92 L, 50-58 L, 106-111 L), and 300-420 L with
  runs of 80-110 min on one unit that likely has a buffer tank;
- on the five units in alert, a small loop (40-58 L) whose emitters absorb about half the
  output, with the compressor at its floor most of the time on four of them; units with
  long cycles have either more than 100 L or emitters absorbing over 75% of the output.

## What to do about an alert

Nearly every heating stop on the fleet is a **thermo-off**: the outlet water reaches
the target plus 5 °C and the unit stops the compressor, then restarts it once the water
is back under the target and at least 3 minutes have passed (service manual SMGB0146,
"Compressor thermo ON/OFF control"). Neither margin is adjustable. A unit that short
cycles is therefore almost always a heating circuit that cannot absorb the unit's
minimum output, and the causes below are the usual reasons why:

1. **A heating curve set too high.** Water hotter than the house needs reaches its
   target sooner, and rooms that overheat close their thermostatic valves. A first
   analysis on raw targets found a clear link (reconstructed curve slope against peak
   starts `rho = -0.53`, `max_flow_temp_heating_otc` ceiling `+0.52`, applied setpoint
   at 10 °C outdoors `+0.38`). A later one, with curves corrected for the Eco offset,
   room compensation and the smoothed outdoor temperature (see discussion
   [#510](https://github.com/alepee/hass-hitachi_yutaki/discussions/510)), found only a
   weak link between curve height and starts per hour. The curve is still the first thing
   to try, because it costs nothing, but it is a lever rather than a proven cause.
2. **Too few open emitters.** When thermostatic radiator valves or zone valves close,
   the unit only heats a small part of the circuit and the water volume it actually sees
   drops, possibly below the manufacturer's minimum (40-50 L on an S80, computed for the
   same 4-5 K on/off differential). An installation where most valves sit closed in
   overheated rooms combines this cause with the first one. Keeping some emitters always
   open gives the unit a load it can rely on.
3. **Too little buffer volume** for the unit's minimum output.
4. **An oversized unit** for the actual demand. Units that cycle are typically already
   pinned at their minimum compressor frequency (the fleet converges on **31 Hz**), so
   there is no modulation margin left to recover. Note the correlation between frequency
   floor and peak starts is **negative** (`-0.55`): cycling units are not units that fail
   to modulate down, they are units that have already run out of room.

Counter-intuitively, units running a **fixed setpoint** (OTC disabled) cycle *less* than
those on a heating curve, by a factor of 3 on the median period (62 min against 18 and
21). Effectives are small (5 and 6 units), so this is a lead, not a rule.

## Limitations

- Calibrated on 14 evaluable units, with a single installation in alert: a coherent
  signal, not a statistical validation.
- **No data below 0 °C outdoors**: behaviour at full winter load is not validated.
- Cooling is not evaluated for persistence (only 3 consecutive days available), though
  cycling looks more severe there.
- DHW cycling is measurable but not surfaced: the actionable advice is weak and the
  intra-unit variability much higher.
- The per-installation diagnosis needs a water flow reading, assumes a roughly steady
  load over a cycle, and reads the loop through the unit's own inlet: a buffer tank or a
  low-loss header can make the return unrepresentative of the emitter circuit. The
  cascade hint has only been observed on one S80 so far.
- HC-A(16/64)MB installations declare a single profile for several units, so the regime
  cannot be determined reliably per unit (see
  [#353](https://github.com/alepee/hass-hitachi_yutaki/issues/353)).
