"""Build per-model refrigerant-charge profiles from the sampled telemetry days.

Signal note: `compressor_tg_gas_temp` is the THMg gas-pipe thermistor, NOT the
suction line — Tg-Te behaves like a lift/discharge-superheat signal (~20-40 K)
in heating, not a suction superheat (2-8 K). Profiles are segmented by
operation mode; `heat` is the segment comparable to RefrigerantMonitor.
"""

import csv
import json
import pathlib
from statistics import median, quantiles

HERE = pathlib.Path(__file__).parent
DAYS = HERE / "data" / "days"
INSTALLS = json.loads((HERE / "data" / "installations.json").read_text())

MIN_FREQ, MAX_FREQ = 20.0, 150.0
MIN_SAMPLES_PER_DAY = 30
SH_CAP_DETECTOR = 40.0  # RefrigerantMonitor SUPERHEAT_MAX_K

MODE_MAP = {
    "operation_state_heat_thermo_on": "heat",
    "operation_state_dhw_on": "dhw",
    "operation_state_cool_thermo_on": "cool",
    "operation_state_pool_on": "pool",
}


def load_points():
    """Yield (hash, day, mode, tg, te, evo, outdoor, freq) for running, plausible points."""
    for f in sorted(DAYS.glob("*.csv")):
        day = f.stem
        with f.open() as fh:
            for row in csv.DictReader(fh):
                mode = MODE_MAP.get(row["op_state"])
                if mode is None:
                    continue
                try:
                    tg = float(row["tg"])
                    te = float(row["te"])
                    evo = float(row["evo"])
                    out = float(row["outdoor"])
                    freq = float(row["freq"])
                except (ValueError, TypeError):
                    continue
                if not (MIN_FREQ <= freq <= MAX_FREQ):
                    continue
                if not (0.0 <= evo <= 100.0):
                    continue
                if not (-60.0 <= te <= 40.0) or not (-40.0 <= out <= 40.0):
                    continue
                if not (-20.0 <= tg <= 100.0):
                    continue
                yield row["hash"], day, mode, tg, te, evo, out, freq


def summarize(rows):
    """Aggregate one instance-mode point list into a profile summary."""
    by_day: dict[str, list[tuple]] = {}
    for r in rows:
        by_day.setdefault(r[0], []).append(r)
    days = []
    for day, drows in sorted(by_day.items()):
        if len(drows) < MIN_SAMPLES_PER_DAY:
            continue
        shs = [r[1] - r[2] for r in drows]
        days.append(
            {
                "day": day,
                "n": len(drows),
                "sh": round(median(shs), 1),
                "evo": round(median(r[3] for r in drows), 1),
                "te": round(median(r[2] for r in drows), 1),
                "outdoor": round(median(r[4] for r in drows), 1),
                "freq": round(median(r[5] for r in drows)),
                "pct_sh_gt40": round(
                    100 * sum(s > SH_CAP_DETECTOR for s in shs) / len(shs)
                ),
            }
        )
    if not days:
        return None
    valid_days = {d["day"] for d in days}
    curve: dict[int, dict[str, list[float]]] = {}
    for day, tg, te, evo, out, _freq in rows:
        if day not in valid_days:
            continue
        b = int(out // 2) * 2
        c = curve.setdefault(b, {"sh": [], "evo": []})
        c["sh"].append(tg - te)
        c["evo"].append(evo)
    shs = [d["sh"] for d in days]
    evos = [d["evo"] for d in days]
    return {
        "n_valid_days": len(days),
        "sh_median": round(median(shs), 1),
        "sh_q1q3": [
            round(q, 1)
            for q in (quantiles(shs, n=4)[0::2] if len(shs) >= 2 else [shs[0], shs[0]])
        ],
        "evo_median": round(median(evos), 1),
        "pct_sh_gt40_overall": round(
            sum(d["pct_sh_gt40"] * d["n"] for d in days) / sum(d["n"] for d in days)
        ),
        "days": days,
        "curve": {
            str(b): {
                "n": len(c["sh"]),
                "sh": round(median(c["sh"]), 1),
                "evo": round(median(c["evo"]), 1),
            }
            for b, c in sorted(curve.items())
            if len(c["sh"]) >= 20
        },
    }


def main():
    pts: dict[tuple[str, str], list[tuple]] = {}
    tg_all: dict[str, list[float]] = {}
    for h, day, mode, tg, te, evo, out, freq in load_points():
        pts.setdefault((h, mode), []).append((day, tg, te, evo, out, freq))
        tg_all.setdefault(h, []).append(tg)

    phantom = {h for h, tgs in tg_all.items() if median(tgs) < 5.0}

    result: dict[str, dict] = {}
    for (h, mode), rows in pts.items():
        if h in phantom:
            continue
        s = summarize(rows)
        if s is None:
            continue
        inst = result.setdefault(
            h, {"profile": INSTALLS.get(h, {}).get("profile", "unknown"), "modes": {}}
        )
        inst["modes"][mode] = s

    out = {"phantom_excluded": sorted(phantom), "instances": result}
    (HERE / "data" / "profiles_per_instance.json").write_text(json.dumps(out, indent=1))

    for mode in ["heat", "dhw", "cool"]:
        by_model: dict[str, list] = {}
        for inst in result.values():
            if mode in inst["modes"]:
                by_model.setdefault(inst["profile"], []).append(inst["modes"][mode])
        if not by_model:
            continue
        print(f"\n=== mode {mode} ===")
        print(
            f"{'model':16} {'inst':>4} {'SH med K':>9} {'SH inst range':>15} {'EVO med %':>9} {'%pts SH>40':>10}"
        )
        for model, insts in sorted(by_model.items()):
            shs = [r["sh_median"] for r in insts]
            evos = [r["evo_median"] for r in insts]
            p40 = [r["pct_sh_gt40_overall"] for r in insts]
            print(
                f"{model:16} {len(insts):>4} {median(shs):>9.1f} "
                f"{f'{min(shs):.0f}..{max(shs):.0f}':>15} {median(evos):>9.1f} "
                f"{f'{min(p40)}..{max(p40)}':>10}"
            )
    print("\nphantom Tg (excluded):", len(phantom))


if __name__ == "__main__":
    main()
