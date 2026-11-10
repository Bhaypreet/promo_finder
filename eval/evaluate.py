"""Compare one or more runs against the hand-picked reference promos (eval/gold.json).

    python eval/evaluate.py outputs/rules-only outputs/gpt-oss-120b

Metrics (only on episodes that have reference promos):
  recall     share of reference promos that some tool promo overlaps (time IoU >= 0.4)
  precision  share of tool promos that overlap some reference promo
  hook_ok    of the matched pairs, share where the tool's clip starts within 3 s of the reference hook
  start/end  mean absolute boundary error (s) of matched pairs
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

IOU = 0.4


def spans(p: dict, ep: int) -> list[tuple[float, float]]:
    return [(s["start"], s["end"]) for s in p["segments"] if s["ep"] == ep]


def iou(a: list[tuple[float, float]], b: tuple[float, float]) -> float:
    inter = sum(max(0.0, min(e, b[1]) - max(s, b[0])) for s, e in a)
    total_a = sum(e - s for s, e in a)
    union = total_a + (b[1] - b[0]) - inter
    return inter / union if union > 0 else 0.0


def evaluate(run_dir: Path, gold: list[dict]) -> dict:
    promos = json.loads((run_dir / "promos.json").read_text(encoding="utf-8"))["promos"]
    gold_eps = {g["ep"] for g in gold}
    singles = [p for p in promos if p["kind"] != "montage" and set(p["episodes"]) <= gold_eps]
    matched, rows = 0, []
    for g in gold:
        best, best_iou = None, 0.0
        for p in singles:
            if g["ep"] not in p["episodes"]:
                continue
            v = iou(spans(p, g["ep"]), (g["start"], g["end"]))
            if v > best_iou:
                best, best_iou = p, v
        hit = best_iou >= IOU
        matched += hit
        row = {"ep": g["ep"], "gold": f"{g['start']:.1f}-{g['end']:.1f}", "iou": round(best_iou, 2), "hit": hit}
        if best is not None:
            s0 = best["segments"][0]["start"]; e1 = best["segments"][-1]["end"]
            row.update({"tool": best["id"], "tool_span": f"{s0:.1f}-{e1:.1f}",
                        "hook_ok": abs(s0 - g["hook"]) <= 3.0, "d_start": round(abs(s0 - g["start"]), 1),
                        "d_end": round(abs(e1 - g["end"]), 1)})
        rows.append(row)
    prec_hits = sum(any(iou(spans(p, g["ep"]), (g["start"], g["end"])) >= IOU for g in gold if g["ep"] in p["episodes"])
                    for p in singles)
    hits = [r for r in rows if r["hit"]]
    return {
        "run": run_dir.name, "reference_promos": len(gold), "tool_promos_on_those_eps": len(singles),
        "recall": round(matched / len(gold), 2),
        "precision": round(prec_hits / max(1, len(singles)), 2),
        "hook_ok": round(sum(r.get("hook_ok", False) for r in hits) / max(1, len(hits)), 2),
        "mean_start_err_s": round(sum(r["d_start"] for r in hits) / max(1, len(hits)), 1),
        "mean_end_err_s": round(sum(r["d_end"] for r in hits) / max(1, len(hits)), 1),
        "rows": rows,
    }


def random_baseline(gold: list[dict], per_ep: int = 2, trials: int = 300) -> dict:
    """Floor for the metrics: `per_ep` random 30-45 s windows per episode."""
    import random
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from promo_finder.parse import load_show
    folder = next(Path(__file__).resolve().parent.parent.glob("data/*/"))
    dur = {e.num: e.duration for e in load_show(folder)}
    rng = random.Random(7)
    keys = ("recall", "precision", "hook_ok", "mean_start_err_s", "mean_end_err_s")
    acc = {k: 0.0 for k in keys}
    tmp = Path(__file__).parent / "_random"
    tmp.mkdir(exist_ok=True)
    for _ in range(trials):
        promos = []
        for ep in sorted({g["ep"] for g in gold}):
            for i in range(per_ep):
                L = rng.uniform(30, 45); s = rng.uniform(0, max(0.0, dur[ep] - L))
                promos.append({"id": f"rand-{ep}-{i}", "kind": "single", "episodes": [ep],
                               "segments": [{"ep": ep, "start": s, "end": s + L}]})
        (tmp / "promos.json").write_text(json.dumps({"promos": promos}), encoding="utf-8")
        r = evaluate(tmp, gold)
        for k in keys:
            acc[k] += r[k] / trials
    return {"run": f"random ({per_ep}/episode, avg of {trials})", **{k: round(v, 2) for k, v in acc.items()},
            "reference_promos": len(gold), "tool_promos_on_those_eps": per_ep * len({g['ep'] for g in gold}), "rows": []}


def main() -> None:
    gold = json.loads((Path(__file__).parent / "gold.json").read_text(encoding="utf-8"))["promos"]
    results = [random_baseline(gold)] + [evaluate(Path(d), gold) for d in sys.argv[1:]]
    for r in results:
        print(f"\n== {r['run']}: recall {r['recall']}  precision {r['precision']}  hook_ok {r['hook_ok']}  "
              f"start err {r['mean_start_err_s']}s  end err {r['mean_end_err_s']}s  "
              f"({r['tool_promos_on_those_eps']} tool promos vs {r['reference_promos']} reference)")
        for row in r["rows"]:
            print("   ", row)
    out = Path(sys.argv[1]).parent / "eval_results.json" if sys.argv[1:] else None
    if out:
        out.write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
