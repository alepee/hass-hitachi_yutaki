"""Roll instance profiles up to per-model refrigerant profiles.

Reads data/profiles_per_instance.json (produced by analyze.py) and writes
data/profiles_per_model.json: per model x mode, the fleet band (median /
min / max of instance medians), the per-instance summaries, and the
SH / EVO vs outdoor-temperature curves (2 degree C bins, median across
instances, bins kept when >= 2 instances contribute).

Instances whose reported profile is `yutampo_r32` are excluded: that model
has no refrigerant-circuit registers, so refrigerant-looking data under that
profile indicates a profile misdetection, not a Yutampo.
"""

import json
import pathlib
from statistics import median

HERE = pathlib.Path(__file__).parent


def main() -> None:
    data = json.loads((HERE / "data" / "profiles_per_instance.json").read_text())

    models: dict[str, dict] = {}
    for h, inst in data["instances"].items():
        p = inst["profile"]
        if p == "yutampo_r32":
            continue
        for mode, s in inst["modes"].items():
            m = models.setdefault(p, {}).setdefault(
                mode, {"instances": [], "curves": {}}
            )
            m["instances"].append(
                {
                    "hash": h[:6],
                    "sh_median": s["sh_median"],
                    "sh_q1q3": s["sh_q1q3"],
                    "evo_median": s["evo_median"],
                    "n_valid_days": s["n_valid_days"],
                    "pct_sh_gt40": s["pct_sh_gt40_overall"],
                }
            )
            for b, c in s["curve"].items():
                bin_ = m["curves"].setdefault(int(b), {"sh": [], "evo": []})
                bin_["sh"].append(c["sh"])
                bin_["evo"].append(c["evo"])

    out: dict[str, dict] = {}
    for p, mm in models.items():
        out[p] = {}
        for mode, m in mm.items():
            min_inst = 2 if len(m["instances"]) >= 3 else 1
            curve = [
                {
                    "t": b,
                    "n_inst": len(c["sh"]),
                    "sh": round(median(c["sh"]), 1),
                    "sh_min": min(c["sh"]),
                    "sh_max": max(c["sh"]),
                    "evo": round(median(c["evo"]), 1),
                    "evo_min": min(c["evo"]),
                    "evo_max": max(c["evo"]),
                }
                for b, c in sorted(m["curves"].items())
                if len(c["sh"]) >= min_inst
            ]
            shs = [i["sh_median"] for i in m["instances"]]
            evos = [i["evo_median"] for i in m["instances"]]
            out[p][mode] = {
                "n_instances": len(m["instances"]),
                "sh_median": round(median(shs), 1),
                "sh_min": min(shs),
                "sh_max": max(shs),
                "evo_median": round(median(evos), 1),
                "evo_min": min(evos),
                "evo_max": max(evos),
                "instances": sorted(m["instances"], key=lambda i: i["sh_median"]),
                "curve": curve,
            }

    (HERE / "data" / "profiles_per_model.json").write_text(json.dumps(out, indent=1))
    for p, mm in sorted(out.items()):
        for mode, m in sorted(mm.items()):
            print(
                f"{p:16} {mode:5} n={m['n_instances']:<3} "
                f"SH {m['sh_median']} [{m['sh_min']}..{m['sh_max']}] K  "
                f"EVO {m['evo_median']} %"
            )


if __name__ == "__main__":
    main()
