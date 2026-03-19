# Hitachi Yutaki Model Nomenclature

This document explains how to decode Hitachi Yutaki model references to identify the hardware generation, capabilities, and which register map applies.

## Why This Matters

The ATW-MBS-02 gateway has **two distinct register maps** depending on the heat pump generation:

- **Before Line-up 2016** — Gen 1 units with a simpler register layout
- **Line-up 2016** — newer units with expanded registers (eco modes, wireless thermostats, etc.)

Using the wrong register map causes misread sensors, write errors, and potential alarm codes. Identifying the exact model generation from the user's reference number is the first step in troubleshooting.

## Indoor Unit Prefixes

Each Yutaki product family uses a distinct indoor unit prefix:

| Prefix | Product Family | Description |
|---|---|---|
| **RWD** | Yutaki S Combi | Split indoor unit with integrated DHW tank |
| **RWM** | Yutaki S | Split indoor unit (no integrated tank) |
| **RWM** | Yutaki S80 (Gen 1) | High-temperature cascade indoor unit |
| **RWH** | Yutaki S80 (Gen 2+) | High-temperature cascade indoor unit (newer) |
| **RASM** | Yutaki M | Monobloc (outdoor unit only, no indoor unit) |
| **RAS** | All families | Outdoor unit |

## Suffix Letter Conventions

Across all families, these letters carry consistent meaning in the model suffix:

| Letter | Meaning | Notes |
|---|---|---|
| **N** | R410A refrigerant | Original refrigerant, pre-R32 transition |
| **R** | R32 refrigerant | Newer, lower-GWP refrigerant |
| **V** | Single-phase (~230V) | Absent = three-phase (3N~400V) |
| **E** | European market | Present on most EU models |
| **W** | Variant modifier | Context-dependent: solar in S Combi Gen 1 (`NW(S)E`), integrated tank in S80, wider range in M |
| **S** | Solar / Stainless steel | In S Combi Gen 1 suffix (`NWSE`): solar variant; in tank suffix (`-220S`): stainless steel |
| **K** | Market variant | UK/specific market variant |
| **H** | High capacity / Heater | In S80 Gen 1: high capacity; in S Combi Gen 4 (`-6H`): 6 kW electric heater |
| **F** | R-134a (cascade) | Used in S80 cascade system alongside N (R-410A) |

The **generation number** appears before the final `E`:
- No number = Gen 1 (e.g., `NWE`, `VNE`)
- `1` = Gen 2 (e.g., `NW1E`, `VR1E`)
- `2` = Gen 3 (e.g., `RW2E`, `VR2E`)
- `3` = Gen 4 (e.g., `RW3E`)

## Yutaki S Combi (prefix: RWD)

Split system with integrated DHW tank. Reference pattern: `RWD-<capacity>.<decimal><suffix>-<tank>`

### Indoor Units

| Suffix | Refrigerant | Generation | Confirmed Models | Register Map |
|---|---|---|---|---|
| **NWE** | R410A | Gen 1 | `RWD-(2.0-6.0)NWE-(200/260)S` | Before Line-up 2016 |
| **NWSE** | R410A | Gen 1 | `RWD-(2.0-6.0)NWSE-(200/260)S` | Before Line-up 2016 |
| **NW1E** | R410A | Gen 2 ("2.0") | `RWD-(4.0-6.0)NW1E-220S(-K)` | Line-up 2016 |
| **RW1E** | R32 | Gen 2 | `RWD-(2.0-3.0)RW1E-220S(-K)` | Line-up 2016 |
| **RW2E** | R32 | Gen 3 | `RWD-(1.5-3.0)RW2E-220S-K` | Line-up 2016 |
| **RW3E** | R32 | Gen 4 | `RWD-(1.5-6.0)RW3E-220S(-K)(-6H)` | Line-up 2016 |

**Notes:**
- Gen 1 `NWE` = standard, `NWSE` = solar variant (with plate heat exchanger)
- Gen 1 tanks: 200L or 260L. Gen 2+: standardized to 220L
- Gen 4 `-6H` suffix indicates a 6 kW electric backup heater
- There is **no** `NW2E` or `NW3E` — the R32 transition changed `N` to `R`

### Paired Outdoor Units

| Suffix | Refrigerant | Phase | Confirmed Models |
|---|---|---|---|
| **WHVNP** | R410A | 1-phase | `RAS-(2-3)WHVNP` |
| **WHVNPE** | R410A | 1-phase | `RAS-(4-6)WHVNPE` |
| **WHNPE** | R410A | 3-phase | `RAS-(4-10)WHNPE` |
| **WHVRP** | R32 | 1-phase | `RAS-(2-3)WHVRP` |
| **WHVRP1** | R32 | 1-phase | `RAS-3WHVRP1` |

Outdoor unit suffix decoding: `WH` = Water Heating, `V` = single-phase, `N` = R410A / `R` = R32, `P` = heat Pump, `E` = Europe.

## Yutaki S (prefix: RWM + RAS)

Split system without integrated tank. Indoor unit uses prefix **RWM** (not RWD).

### Indoor Units

| Suffix | Refrigerant | Generation | Confirmed Models | Register Map |
|---|---|---|---|---|
| **NE** | R410A | Gen 1 | `RWM-(2.0-10.0)NE` | Before Line-up 2016 |
| **N1E** | R410A | Gen 2 | `RWM-(4.0-10.0)N1E` | Line-up 2016 |
| **R1E** | R32 | Gen 2 | `RWM-(2.0-3.0)R1E` | Line-up 2016 |

### Paired Outdoor Units

Same outdoor units as Yutaki S Combi (see table above).

## Yutaki S80 (prefix: RWM Gen 1, RWH Gen 2+)

High-temperature cascade system (R410A + R134a). The indoor unit prefix changed from **RWM** (Gen 1) to **RWH** (Gen 2+).

### Indoor Units

| Suffix | Generation | Confirmed Models | Register Map |
|---|---|---|---|
| **FSN3E** | Gen 1 | `RWM-(4.0-6.0)FSN3E` | Line-up 2016 |
| **HFSN3E** | Gen 1 (high cap.) | `RWM-6.0HFSN3E` | Line-up 2016 |
| **VNFE** | Gen 2 (1-phase) | `RWH-(4.0-6.0)VNFE` | Line-up 2016 |
| **NFE** | Gen 2 (3-phase) | `RWH-(4.0-6.0)NFE` | Line-up 2016 |
| **VNFWE** | Gen 2 (1-ph, tank) | `RWH-(4.0-6.0)VNFWE` | Line-up 2016 |
| **NFWE** | Gen 2 (3-ph, tank) | `RWH-(4.0-6.0)NFWE` | Line-up 2016 |

**Notes:**
- S80 suffix `F` indicates R-134a (second refrigerant in the cascade)
- Gen 2 suffix `W` = integrated DHW tank variant (Type 2)
- All known S80 models use the Line-up 2016 register map (the S80 was introduced in the 2016 lineup)

### Paired Outdoor Units

| Suffix | Phase | Confirmed Models |
|---|---|---|
| **HVRNME-AF** | 1-phase | `RAS-(4-6)HVRNME-AF` |
| **HRNME-AF** | 3-phase | `RAS-(4-6)HRNME-AF` |

## Yutaki M (prefix: RASM)

Monobloc system (single outdoor unit, no indoor unit). Reference pattern: `RASM-<capacity><suffix>`

| Suffix | Refrigerant | Generation | Confirmed Models | Register Map |
|---|---|---|---|---|
| **VNE** | R410A | Gen 1 (1-phase) | `RASM-(3-6)VNE` | Before Line-up 2016 |
| **NE** | R410A | Gen 1 (3-phase) | `RASM-(3-6)NE` | Before Line-up 2016 |
| **VRE** | R32 | Gen 2 (1-phase) | `RASM-(2-3)VRE` | Line-up 2016 |
| **VR1E** | R32 | Gen 3 (1-phase) | `RASM-(4-6)VR1E` | Line-up 2016 |
| **RW1E** | R32 | Gen 3 (3-phase) | `RASM-(4-7)RW1E` | Line-up 2016 |
| **VR2E** | R32 | Gen 4 (1-phase) | `RASM-(2-3)VR2E` | Line-up 2016 |

**Notes:**
- There is **no** `RASM-*N1E` — the R32 transition changed `N` to `R`
- `V` = single-phase, absent = three-phase

## Controllers

The controller (LCD remote) is **independent** from the heat pump generation. A newer controller can be retrofitted onto an older unit. Do not use the controller model to determine the register map.

| Controller | Era | Notes |
|---|---|---|
| PC-ARFH1E | Original | Monochrome LCD, original generation |
| PC-ARFH2E | 2021+ | Newer monochrome LCD, retro-compatible with all Yutaki models |
| PC-ARFH3E | Recent | Color touchscreen |
| PC-S80TE | S80 specific | Cascade controller for S80 models |

## Quick Identification Flowchart

When a user reports an issue, ask for the **indoor unit reference** (on the nameplate or in the manual):

1. **Identify the prefix** to determine the product family (`RWD` = S Combi, `RWM` = S or S80 Gen 1, `RWH` = S80 Gen 2+, `RASM` = M)
2. **Extract the suffix** (e.g., `NWSE` from `RWD-4.0NWSE-260S`)
3. **Check the refrigerant letter**: `N` = R410A (older), `R` = R32 (newer)
4. **Check the generation number** before the final `E`: none = Gen 1, `1` = Gen 2, `2` = Gen 3, `3` = Gen 4
5. **Determine the register map**: Gen 1 with `N` (R410A) and no generation number → Before Line-up 2016; all others → Line-up 2016
6. **If uncertain**, ask the user to run the gateway scanner script — the scan output will confirm which registers are active

### Common Pitfalls

- **Recent purchase ≠ recent generation**: users may buy old stock or have units installed years after manufacturing
- **New controller on old unit**: the PC-ARFH2E (2021+) is retro-compatible, so a "new-looking" controller does not mean a new heat pump
- **"2020 model"**: the user may refer to the installation date, not the hardware generation
- **Indoor unit prefix matters**: `RWD` is only for S Combi; Yutaki S uses `RWM`, S80 uses `RWM` or `RWH`
- **N vs R confusion**: the refrigerant letter (N=R410A, R=R32) is often the key to distinguishing generations

## Sources

- [Yutaki S Combi Gen 1 IOM](https://ultimateair.co.uk/wp-content/uploads/2023/10/IOM_YUTAKI_S_COMBI.pdf) — `RWD-(2.0-6.0)NW(S)E-(200/260)S(-K)(-W)`
- [Yutaki S Gen 2 IOM](https://documentation.hitachiaircon.com/glb/en/heating/rwm-n-r-1e-w) — `RWM-(2.0-10.0)(N/R)1E`
- [Yutaki S Combi Gen 2 IOM](https://documentation.hitachiaircon.com/glb/en/heating/rwd-n-r-w1e-s-k) — `RWD-(N/R)W1E`
- [Yutaki S Combi Gen 3+](https://documentation.hitachiaircon.com/glb/en/heating/rwd-rw2e-220-s-k-6h) — `RWD-RW2E/RW3E`
- [Yutaki M R410A](https://documentation.hitachiaircon.com/glb/en/heating/rasm-v-r-n-e) — `RASM-(V)(N)E`
- [Yutaki M R32](https://documentation.hitachiaircon.com/glb/en/heating/rasm-v-r-w-1e) — `RASM-(V)(R)(W)1E`
- [Yutaki S80 Gen 1](https://documentation.hitachiaircon.com/glb/en/heating/rwm-h-fsn3e) — `RWM-(H)FSN3E`
- [Yutaki S80 Gen 2](https://documentation.hitachiaircon.com/glb/en/heating/rwh-v-nf-w-e) — `RWH-(V)NF(W)E`
- [Yutaki Outdoor Units](https://documentation.hitachiaircon.com/glb/en/heating/ras-wh-v-r-n-p-e) — `RAS-WH(V)(N/R)P(1)(E)`

## See Also

- [ATW-MBS-02 Register Maps](../gateway/atw-mbs-02.md) — full register tables for both generations
- [Heat Pump Profiles](../development/profiles.md) — how profiles are detected and configured
- [Scan Reference](../gateway/scan-reference.md) — interpreting gateway scan output
