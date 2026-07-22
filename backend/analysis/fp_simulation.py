"""Replay the RefrigerantMonitor decision rule on real fleet data.

The fleet is presumed healthy over the analysed window, so every alert
condition produced by the replay is a false positive, and the share of
instances stuck without a baseline measures detector availability.

Faithful to domain/services/refrigerant.py:
  - qualifying samples: heating mode, frequency 20-150 Hz, plausibility ranges
    (the SH cap is a parameter: 40 K as shipped, 80 K proposed);
  - valid day: >= 30 qualifying samples, daily aggregate = medians;
  - baseline: frozen over the first 14 valid days;
  - verdict: recent = last 7 valid days (>= 3), delta_SH vs baseline;
    WATCH at >= 3 K; ALERT at >= 5 K corroborated by delta_EVO >= 15 pts over
    recent days outdoor-matched to the baseline (±4 K, >= 3 matched);
  - repair issue: ALERT on >= 3 consecutive valid days.

Meaningful only on CONSECUTIVE heating-season days (see README.md).
"""

import csv
import json
import pathlib
from statistics import median

HERE = pathlib.Path(__file__).parent
DAYS = HERE / "data" / "days"
INSTALLS = json.loads((HERE / "data" / "installations.json").read_text())

MIN_FREQ, MAX_FREQ = 20.0, 150.0
MIN_SAMPLES_PER_DAY = 30
BASELINE_DAYS = 14
EVAL_DAYS = 7
MIN_EVAL_DAYS = 3
TEMP_MATCH_K = 4.0
SUPERHEAT_WATCH_K = 3.0
SUPERHEAT_ALERT_K = 5.0
EVO_ALERT_PCT = 15.0
ALERT_PERSIST_DAYS = 3


def daily_aggregates(sh_cap: float) -> dict[str, list[tuple]]:
    """Return {hash: [(day, sh, evo, outdoor), ...]} for heating mode."""
    buf: dict[tuple[str, str], dict[str, list[float]]] = {}
    for f in sorted(DAYS.glob("*.csv")):
        day = f.stem
        with f.open() as fh:
            for row in csv.DictReader(fh):
                if row["op_state"] != "operation_state_heat_thermo_on":
                    continue
                try:
                    tg, te = float(row["tg"]), float(row["te"])
                    evo, out = float(row["evo"]), float(row["outdoor"])
                    freq = float(row["freq"])
                except (ValueError, TypeError):
                    continue
                if not (MIN_FREQ <= freq <= MAX_FREQ):
                    continue
                sh = tg - te
                if not (-10.0 <= sh <= sh_cap):
                    continue
                if not (0.0 <= evo <= 100.0) or not (-60.0 <= te <= 40.0):
                    continue
                d = buf.setdefault((row["hash"], day), {"sh": [], "evo": [], "out": []})
                d["sh"].append(sh)
                d["evo"].append(evo)
                d["out"].append(out)
    result: dict[str, list[tuple]] = {}
    for (h, day), v in sorted(buf.items()):
        if len(v["sh"]) < MIN_SAMPLES_PER_DAY:
            continue
        result.setdefault(h, []).append(
            (day, median(v["sh"]), median(v["evo"]), median(v["out"]))
        )
    return result


def simulate(sh_cap: float, label: str) -> None:
    aggs = daily_aggregates(sh_cap)
    n_inst = with_baseline = evals = watch = alert_cond = issues = 0
    detail = []
    for h, days in sorted(aggs.items()):
        profile = INSTALLS.get(h, {}).get("profile", "?")
        if profile == "yutampo_r32":
            continue
        n_inst += 1
        if len(days) < BASELINE_DAYS + MIN_EVAL_DAYS:
            continue
        with_baseline += 1
        base = days[:BASELINE_DAYS]
        b_sh = median(d[1] for d in base)
        b_evo = median(d[2] for d in base)
        b_out = median(d[3] for d in base)
        inst_watch = inst_alert = inst_evals = streak = inst_issues = 0
        worst = 0.0
        for i in range(BASELINE_DAYS + MIN_EVAL_DAYS, len(days) + 1):
            recent = days[max(0, i - EVAL_DAYS) : i]
            if len(recent) < MIN_EVAL_DAYS:
                continue
            inst_evals += 1
            d_sh = median(d[1] for d in recent) - b_sh
            worst = max(worst, d_sh)
            matched = [d for d in recent if abs(d[3] - b_out) <= TEMP_MATCH_K]
            d_evo = (
                median(d[2] for d in matched) - b_evo
                if len(matched) >= MIN_EVAL_DAYS
                else None
            )
            if (
                d_sh >= SUPERHEAT_ALERT_K
                and d_evo is not None
                and d_evo >= EVO_ALERT_PCT
            ):
                inst_alert += 1
                streak += 1
                if streak == ALERT_PERSIST_DAYS:
                    inst_issues += 1
            else:
                streak = 0
                if d_sh >= SUPERHEAT_WATCH_K:
                    inst_watch += 1
        evals += inst_evals
        watch += inst_watch
        alert_cond += inst_alert
        issues += inst_issues
        flag = " <-- would raise repair issue" if inst_issues else ""
        if inst_watch or inst_alert:
            detail.append(
                f"    {profile} {h[:6]}: {len(days)} valid days, worst dSH +{worst:.1f} K, "
                f"watch {inst_watch}/{inst_evals} d, alert {inst_alert}/{inst_evals} d{flag}"
            )
    print(f"\n== {label} (SH cap {sh_cap:.0f} K) ==")
    print(f"  instances with heating data: {n_inst}")
    if n_inst:
        print(
            f"  reaching a baseline (>= {BASELINE_DAYS + MIN_EVAL_DAYS} valid days): "
            f"{with_baseline} ({100 * with_baseline / n_inst:.0f}% availability)"
        )
    if evals:
        print(
            f"  instance-day verdicts: {evals} | WATCH: {watch} ({100 * watch / evals:.1f}%) | "
            f"ALERT condition: {alert_cond} ({100 * alert_cond / evals:.1f}%) | repair issues: {issues}"
        )
    for line in detail:
        print(line)


if __name__ == "__main__":
    simulate(40.0, "as shipped")
    simulate(80.0, "proposed fix")
