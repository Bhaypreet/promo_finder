"""Deterministic guardrails: beat IDs -> frame-safe timestamps, hard-rule checks and automatic repairs.
The model never does arithmetic on time; this module does all of it."""
from __future__ import annotations

from .heuristics import HOOK_WINDOW, MAX_LEN, MIN_LEN, beat_scores, snap_end, snap_start
from .parse import Episode, fmt
from .schemas import Promo, PromoPick, Segment


def build_segment(ep: Episode, start_beat: str, end_beat: str) -> Segment | str:
    sb, eb = ep.beat(start_beat), ep.beat(end_beat)
    if sb is None or eb is None:
        return f"unknown beat ID {start_beat if sb is None else end_beat}"
    if eb.end <= sb.start:
        return f"segment {start_beat}-{end_beat} ends before it starts"
    s = snap_start(ep, sb.start, slack=0.6)
    e = snap_end(ep, eb.end)
    cut = [b for b in ep.beats if b.kind == "LINE" and b.start < e < b.end]
    if cut:                                                 # never end inside a spoken line
        e = snap_end(ep, max(b.end for b in cut))
    return Segment(ep=ep.num, start=s, end=e, start_beat=sb.id, end_beat=eb.id)


def promo_from_pick(pick: PromoPick, ep: Episode, pid: str, model: str, patterns: list[str]) -> tuple[Promo | None, list[str]]:
    segs, errs = [], []
    for sp in pick.segments:
        r = build_segment(ep, sp.start_beat, sp.end_beat)
        (errs.append(r) if isinstance(r, str) else segs.append(r))
    if not segs:
        return None, errs or ["no valid segments"]
    segs.sort(key=lambda s: s.start)
    p = Promo(id=pid, kind="single" if len(segs) == 1 else "multi-moment", segments=segs, title=pick.title,
              hook=pick.hook, cliffhanger=pick.cliffhanger, why=pick.why, pattern=pick.pattern,
              hook_beat=pick.hook_beat, cliffhanger_beat=pick.cliffhanger_beat,
              scores={"hook": pick.hook_score, "cliffhanger": pick.cliffhanger_score, "standalone": pick.standalone_score},
              spoiler_risk=pick.spoiler_risk, context_needed=pick.context_needed, model=model,
              retrieved_patterns=patterns)
    return p, errs


def check(p: Promo, eps: dict[int, Episode]) -> list[str]:
    errs = []
    d = p.duration
    if d < MIN_LEN:
        errs.append(f"too short ({d:.1f}s < {MIN_LEN:.0f}s)")
    if d > MAX_LEN:
        errs.append(f"too long ({d:.1f}s > {MAX_LEN:.0f}s)")
    for a, b in zip(p.segments, p.segments[1:]):
        if (a.ep, a.start) > (b.ep, b.start):
            errs.append("segments out of story order")
        if a.ep == b.ep and b.start < a.end - 0.05:
            errs.append("segments overlap")
    first = p.segments[0]
    ep = eps[first.ep]
    hb = ep.beat(p.hook_beat) if p.hook_beat and p.kind != "montage" else None
    if hb is not None:
        gap = hb.start - first.start
        if gap > HOOK_WINDOW + 0.05 or gap < -0.6:
            errs.append(f"hook beat {hb.id} starts {gap:.1f}s into the clip (must be within 3s)")
    else:
        nb = [b for b in ep.beats if b.kind != "CAMERA" and b.start >= first.start - 0.05]
        if nb and nb[0].start - first.start > HOOK_WINDOW:
            errs.append("nothing happens in the first 3s")
    return errs


def auto_fix(p: Promo, eps: dict[int, Episode]) -> None:
    """Repairs that need no model: trim the start onto the hook, cut the end onto the cliffhanger."""
    ep = eps[p.segments[0].ep]
    first = p.segments[0]
    hb = ep.beat(p.hook_beat) if p.hook_beat else None
    if hb and first.start <= hb.start <= first.end and hb.start - first.start > HOOK_WINDOW:
        new_s = snap_start(ep, hb.start, slack=0.6)
        if p.duration - (new_s - first.start) >= MIN_LEN:
            p.fixes.append(f"trimmed start {fmt(first.start)} -> {fmt(new_s)} so the hook lands in the first 3s")
            first.start = new_s
    last = p.segments[-1]
    lep = eps[last.ep]
    cb = lep.beat(p.cliffhanger_beat) if p.cliffhanger_beat else None
    if cb and last.start < cb.end < last.end - 2.0:
        new_e = snap_end(lep, cb.end)
        if new_e < last.end and p.duration - (last.end - new_e) >= MIN_LEN:
            p.fixes.append(f"cut end {fmt(last.end)} -> {fmt(new_e)} to land on the cliffhanger")
            last.end = new_e


def rules_quality(p: Promo, eps: dict[int, Episode]) -> float:
    """Keyword scorer's independent opinion of any promo (0-1)."""
    first, last = p.segments[0], p.segments[-1]
    e0, e1 = eps[first.ep], eps[last.ep]
    s0, s1 = beat_scores(e0), beat_scores(e1)
    hook = max((s0[b.id][0] for b in e0.beats if first.start <= b.start <= first.start + HOOK_WINDOW), default=0)
    cliff = max((s1[b.id][1] for b in e1.beats if last.end - 4 <= b.end <= last.end + 0.01), default=0)
    return round(0.5 * hook + 0.5 * cliff, 3)


def clip_text(p: Promo, eps: dict[int, Episode]) -> str:
    """What a viewer would see/hear, for the blind check: no beat IDs, no show context."""
    out, t0 = [], 0.0
    for i, s in enumerate(p.segments):
        if i:
            out.append("--- CUT ---")
        for b in eps[s.ep].beats:
            if s.start - 1e-6 <= b.start < s.end and b.kind != "CAMERA":
                who = {"ACTION": "ACTION", "SOUND": "SOUND"}.get(b.kind, b.speaker)
                tone = f" ({b.tone})" if b.tone else ""
                flag = "[0-3s] " if t0 + (b.start - s.start) <= HOOK_WINDOW else ""
                out.append(f"{flag}{who}{tone}: {b.text}")
        t0 += s.duration
    return "\n".join(out)
