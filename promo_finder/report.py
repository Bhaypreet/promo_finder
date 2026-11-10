"""Outputs: promos_cutlist.csv (pandas; editor's cut list), promos.md (review sheet), promos.json (everything)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .parse import fmt
from .schemas import Promo


def seg_str(p: Promo) -> str:
    return " + ".join(f"Ep{s.ep} {fmt(s.start)}-{fmt(s.end)}" for s in p.segments)


def write_outputs(out: Path, show: str, promos: list[Promo], log: list, meta: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    payload = {"show": show, "meta": meta,
               "promos": [p.model_dump() | {"duration": p.duration, "episodes": p.episodes,
                                            "segments_ts": [[s.ep, fmt(s.start), fmt(s.end)] for s in p.segments]}
                          for p in promos],
               "log": log}
    (out / "promos.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    rows = []
    for p in promos:
        b = p.blind
        for i, s in enumerate(p.segments, 1):
            rows.append({"rank": p.rank, "promo_id": p.id, "kind": p.kind, "total_sec": p.duration, "segment": i,
                         "episode": s.ep, "start": fmt(s.start), "end": fmt(s.end), "segment_sec": s.duration,
                         "start_beat": s.start_beat, "end_beat": s.end_beat, "hook": p.hook,
                         "cliffhanger": p.cliffhanger, "why": p.why, "pattern": p.pattern,
                         "final_score": p.final_score, "checks_passed": p.passed,
                         "blind_stop": b.stop_scrolling if b else None, "blind_want_next": b.want_next if b else None,
                         "blind_understood": b.understood if b else None, "spoiler_risk": p.spoiler_risk,
                         "model": p.model, "auto_fixes": " | ".join(p.fixes)})
    pd.DataFrame(rows).to_csv(out / "promos_cutlist.csv", index=False, encoding="utf-8")

    u = meta.get("usage", {})
    calls = sum(v["calls"] for v in u.values())
    cached = sum(v.get("cache_hits", 0) for v in u.values())
    lines = [f"# Promo picks: {show}", "",
             f"Picker: `{meta.get('picker')}` | blind viewer: `{meta.get('viewer')}` | episodes: {meta.get('episodes')} | "
             f"promos: {len(promos)} | pass all checks: {sum(p.passed for p in promos)} | LLM calls: {calls} new + {cached} from cache | "
             f"runtime: {meta.get('seconds')} s", "",
             "| # | id | segments | sec | hook | cliffhanger | score | blind stop/next/understood |",
             "|---|---|---|---|---|---|---|---|"]
    for p in promos:
        b = p.blind
        bl = f"{b.stop_scrolling}/{b.want_next}/{b.understood}" if b else "-"
        lines.append(f"| {p.rank} | {p.id}{'' if p.passed else ' ⚠'} | {seg_str(p)} | {p.duration:.0f} | "
                     f"{_md(p.hook)} | {_md(p.cliffhanger)} | {p.final_score:.2f} | {bl} |")
    lines += ["", "## Details", ""]
    for p in promos:
        lines += [f"### {p.rank}. {p.id}: {p.title} ({p.duration:.1f}s, {p.kind})",
                  f"- **Segments:** {seg_str(p)}", f"- **Hook:** {p.hook}", f"- **Cliffhanger:** {p.cliffhanger}",
                  f"- **Why:** {p.why}",
                  f"- **Scores:** {p.scores} | rules {p.rules_score} | spoiler {p.spoiler_risk} | pattern: {p.pattern}",
                  f"- **Retrieved for grounding:** {', '.join(p.retrieved_patterns) or '-'}"]
        if p.context_needed:
            lines.append(f"- **What a new viewer lacks:** {p.context_needed}")
        if p.blind:
            lines.append(f"- **Blind viewer:** \"{p.blind.what_is_happening}\" Confused by: "
                         f"{'; '.join(p.blind.confused_by) or 'nothing'}")
        if p.fixes:
            lines.append(f"- **Fixes:** {'; '.join(p.fixes)}")
        if not p.passed:
            lines.append(f"- **FAILED CHECKS:** {'; '.join(p.problems)}")
        lines.append("")
    (out / "promos.md").write_text("\n".join(lines), encoding="utf-8")


def _md(s: str) -> str:
    return (s or "").replace("|", "/").replace("\n", " ")[:140]
