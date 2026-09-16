# Compressor short-cycling detection

**Status:** beta, opt-in and off by default (`CONF_CYCLING_DETECTION`).
Part of the [preventive maintenance](preventive-maintenance.md) family.

Short cycling is a compressor that starts and stops too often. It wears the compressor,
costs seasonal efficiency, and points at an installation problem rather than a fault in
the machine itself.

> **Advisory.** The detector says *that* the unit cycles, and offers the usual causes in
> order of likelihood. It cannot tell them apart on its own.

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
  wrong.
- **First observed state**: the state the detector wakes up in is never counted as a
  start; there is no transition timestamp to measure a period from.

Intra-day measurements are deliberately **not persisted**: a restart mid-day cannot
reconstruct transitions it did not see. Daily aggregates and the alert streak are
persisted in a `Store`.

## What to do about an alert

In decreasing order of likelihood on the fleet:

1. **A heating curve set too high.** The steeper the curve, the more the installation
   cycles. Measured across the fleet: reconstructed curve slope against peak starts
   `rho = -0.53` (the slope being negative by construction, steeper means more cycling),
   `max_flow_temp_heating_otc` ceiling `+0.52`, applied setpoint at 10 °C outdoors
   `+0.38`. Lowering the flow temperature is the first thing to try and it costs nothing.
2. **Too little buffer volume** for the unit's minimum output.
3. **An oversized unit** for the actual demand. Units that cycle are typically already
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
- HC-A(16/64)MB installations declare a single profile for several units, so the regime
  cannot be determined reliably per unit (see
  [#353](https://github.com/alepee/hass-hitachi_yutaki/issues/353)).
