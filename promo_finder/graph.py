"""LangGraph orchestration.

Main graph
    load ─► index ─► [Send ×N] episode ─► montage ─► [Send ×M] viewer ─► rank ─► (review) ─► END

Episode sub-graph (one per episode, run in parallel through Send)
    retrieve_patterns ─► pick ─► check ──(rule broken & attempts < 1)──► repair ─► check
                                    └──────────────(all good)──────────► finish

* retrieve_patterns  RAG over the promo playbook (FAISS + FastEmbed)
* pick / repair      LLM with Pydantic structured output (EpisodePicks)
* check              code: beat IDs -> timestamps, hard rules, auto-fixes; conditional routing
* montage            hybrid RAG over every moment of the show -> LLM composes cross-episode promos
* viewer             a second, different model judges each clip with zero context
* review             optional human-in-the-loop: interrupt() hands the ranked list to an editor;
                     approved promos are written back into the playbook knowledge base
"""
from __future__ import annotations

import json
import operator
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt

from . import prompts
from .heuristics import candidate_windows, snap_end
from .llm import LLM
from .parse import Episode, fmt, load_show
from .rag import KB, MomentIndex, PlaybookIndex
from .schemas import BlindVerdict, EpisodePicks, MontagePlans, Promo, Segment
from .validate import auto_fix, check, clip_text, promo_from_pick, rules_quality


@dataclass
class Resources:
    show: str
    picker: LLM | None                 # None => rules-only mode, no model at all
    viewer: LLM | None
    playbook: PlaybookIndex | None
    montage: bool = True
    review: bool = False
    moments: MomentIndex | None = None


def merge(a: dict, b: dict) -> dict:
    return {**a, **b}


class ShowState(TypedDict, total=False):
    folder: str
    only: list[int] | None
    episodes: list[Episode]
    promos: Annotated[list[Promo], operator.add]
    verdicts: Annotated[dict, merge]
    log: Annotated[list[dict], operator.add]
    ranked: list[Promo]
    approved: list[str]


class EpisodeState(TypedDict, total=False):
    episode: Episode
    patterns: list[str]
    pattern_text: str
    user: str
    candidates: list[Promo]
    errors: dict
    attempts: int
    model: str
    promos: list[Promo]
    log: list[dict]


# ======================================================================= episode sub-graph
def build_episode_graph(R: Resources):
    def retrieve_patterns(s: EpisodeState) -> dict:
        ep = s["episode"]
        if R.playbook is None:
            return {"patterns": [], "pattern_text": "(playbook disabled)"}
        wins = candidate_windows(ep, top_k=1)
        query = ep.logline + (" " + wins[0].hook_text + " " + wins[0].cliff_text if wins else "")
        docs = R.playbook.retrieve(query, k=3)
        return {"patterns": [d.metadata["name"] for d in docs],
                "pattern_text": "\n".join(f"- {d.page_content}" for d in docs)}

    def pick(s: EpisodeState) -> dict:
        ep = s["episode"]
        sugg = "\n".join(f"- {w.start_beat}..{w.end_beat} ({w.start:.1f}-{w.end:.1f}s, {w.duration:.0f}s) "
                         f"opens: \"{w.hook_text[:70]}\" / ends: \"{w.cliff_text[:70]}\""
                         for w in candidate_windows(ep, top_k=3)) or "(none)"
        user = prompts.PICKER_USER.format(show=R.show, num=ep.num, duration=ep.duration, logline=ep.logline,
                                          patterns=s["pattern_text"], suggestions=sugg, transcript=ep.transcript())
        try:
            picks, model = R.picker.structured(EpisodePicks, prompts.PICKER_SYSTEM, user)
        except Exception as e:
            return {"user": user, "candidates": [], "errors": {}, "attempts": 0,
                    "log": [{"ep": ep.num, "stage": "pick", "error": str(e)[:300]}]}
        cands = []
        log = [{"ep": ep.num, "stage": "pick", "note": picks.skipped_reason}] if picks.skipped_reason else []
        for i, pk in enumerate(picks.promos[:3]):
            p, errs = promo_from_pick(pk, ep, f"E{ep.num:02d}-P{i+1}", model, s["patterns"])
            if p is None:
                log.append({"ep": ep.num, "stage": "pick", "error": f"P{i+1}: {errs}"})
                continue
            p.problems = errs
            cands.append(p)
        return {"user": user, "candidates": cands, "attempts": 0, "model": model, "log": log}

    def check_node(s: EpisodeState) -> dict:
        ep = s["episode"]
        eps = {ep.num: ep}
        errors = {}
        for p in s["candidates"]:
            if not p.problems:
                auto_fix(p, eps)
            p.problems = p.problems + [e for e in check(p, eps) if e not in p.problems]
            if p.problems:
                errors[p.id] = p.problems
        return {"errors": errors}

    def route(s: EpisodeState) -> str:
        return "repair" if s.get("errors") and s.get("attempts", 0) < 1 else "finish"

    def repair(s: EpisodeState) -> dict:
        ep = s["episode"]
        cands = list(s["candidates"])
        log = []
        for pid, errs in s["errors"].items():
            idx = next(i for i, p in enumerate(cands) if p.id == pid)
            bad = cands[idx]
            segs = ", ".join(f"{g.start_beat}-{g.end_beat}" for g in bad.segments)
            user = prompts.REPAIR_USER.format(original=s["user"], title=bad.title, errors="; ".join(errs), segments=segs)
            try:
                picks, model = R.picker.structured(EpisodePicks, prompts.PICKER_SYSTEM, user)
            except Exception as e:
                log.append({"ep": ep.num, "promo": pid, "stage": "repair", "error": str(e)[:300]})
                continue
            fixed = picks.promos[min(idx, len(picks.promos) - 1)] if picks.promos else None
            if fixed is None:
                continue
            p, perrs = promo_from_pick(fixed, ep, pid, model, s["patterns"])
            if p is not None:
                p.problems = perrs
                p.fixes.insert(0, "model repaired it after validator feedback: " + "; ".join(errs))
                cands[idx] = p
            log.append({"ep": ep.num, "promo": pid, "stage": "repair", "errors_before": errs})
        return {"candidates": cands, "attempts": s.get("attempts", 0) + 1, "log": s.get("log", []) + log}

    def finish(s: EpisodeState) -> dict:
        ep = s["episode"]
        out = []
        for p in s["candidates"]:
            p.passed = not p.problems
            p.rules_score = rules_quality(p, {ep.num: ep})
            out.append(p)
        return {"promos": out}

    g = StateGraph(EpisodeState)
    g.add_node("retrieve_patterns", retrieve_patterns)
    g.add_node("pick", pick)
    g.add_node("check", check_node)
    g.add_node("repair", repair)
    g.add_node("finish", finish)
    g.add_edge(START, "retrieve_patterns")
    g.add_edge("retrieve_patterns", "pick")
    g.add_edge("pick", "check")
    g.add_conditional_edges("check", route, {"repair": "repair", "finish": "finish"})
    g.add_edge("repair", "check")
    g.add_edge("finish", END)
    return g.compile()


# ======================================================================= main graph
def build_graph(R: Resources):
    episode_graph = build_episode_graph(R) if R.picker else None

    def load(s: ShowState) -> dict:
        eps = load_show(s["folder"])
        if s.get("only"):
            eps = [e for e in eps if e.num in set(s["only"])]
        return {"episodes": eps, "log": [{"stage": "load", "episodes": len(eps),
                                          "beats": sum(len(e.beats) for e in eps)}]}

    def index(s: ShowState) -> dict:
        if R.picker and R.montage:
            R.moments = MomentIndex(s["episodes"])
            return {"log": [{"stage": "index", "moments": len(R.moments.moments)}]}
        return {}

    def fan_out(s: ShowState):
        return [Send("episode", {"episode": ep}) for ep in s["episodes"]]

    def episode(s: dict) -> dict:
        ep: Episode = s["episode"]
        if episode_graph is None:                      # rules-only mode
            out = []
            for i, w in enumerate(candidate_windows(ep, top_k=2)):
                p = Promo(id=f"R-E{ep.num:02d}-{i+1}", kind="rules", title=f"Ep {ep.num} window {i+1}",
                          segments=[Segment(ep=ep.num, start=w.start, end=w.end, start_beat=w.start_beat, end_beat=w.end_beat)],
                          hook=w.hook_text, cliffhanger=w.cliff_text, rules_score=w.score, model="rules",
                          why=f"rules: hook {w.hook:.2f}, cliff {w.cliff:.2f}, standalone {w.standalone:.2f}"
                              + (f" ({'; '.join(w.notes)})" if w.notes else ""))
                p.problems = check(p, {ep.num: ep})
                p.passed = not p.problems
                out.append(p)
            return {"promos": out}
        res = episode_graph.invoke({"episode": ep})
        print(f"  ep {ep.num:>2}: {len(res.get('promos', []))} promos", flush=True)
        return {"promos": res.get("promos", []), "log": res.get("log", [])}

    def montage(s: ShowState) -> dict:
        if not (R.picker and R.montage and R.moments):
            return {}
        eps = {e.num: e for e in s["episodes"]}
        early = max(eps) if len(eps) < 10 else sorted(eps)[min(len(eps) - 1, 19)]   # spoiler guard: first 20 eps
        slots = [("hook", "hook", 0.0), ("escalation", None, 0.0), ("cliffhanger", "cliff", 0.3)]
        pool: list[dict] = []
        for stage, key, min_cliff in slots:
            for q in R.playbook.query_for_slot(stage)[:4] if R.playbook else []:
                for m in R.moments.search(q, k=2, max_ep=early, rule_key=key, min_cliff=min_cliff):
                    if not any(o["ep"] == m["ep"] and min(o["end"], m["end"]) > max(o["start"], m["start"]) for o in pool):
                        pool.append(m | {"slot": stage})
        pool = sorted(pool, key=lambda m: -m["score"])[:14]
        pool.sort(key=lambda m: (m["ep"], m["start"]))
        for i, m in enumerate(pool):
            m["id"] = f"M{i:03d}"
        by_id = {m["id"]: m for m in pool}
        premise = "\n".join(f"Ep {n}: {eps[n].logline}" for n in sorted(eps)[:4])
        text = "\n".join(f"{m['id']} | ep {m['ep']} | {m['end'] - m['start']:.0f}s | {m['slot']} | {m['text'][:260]}"
                         for m in pool)
        try:
            plans, model = R.picker.structured(MontagePlans, prompts.MONTAGE_SYSTEM,
                                               prompts.MONTAGE_USER.format(show=R.show, premise=premise, moments=text))
        except Exception as e:
            return {"log": [{"stage": "montage", "error": str(e)[:300]}]}
        out, log = [], [{"stage": "montage", "retrieved": [(m["id"], m["ep"], m["slot"], m["score"]) for m in pool]}]
        for i, mp in enumerate(plans.montages[:3]):
            ms = [by_id[x.strip().upper()] for x in mp.moment_ids if x.strip().upper() in by_id]
            if len(ms) < 2:
                log.append({"stage": "montage", "error": f"plan {i+1} used unknown moment IDs {mp.moment_ids}"})
                continue
            ms.sort(key=lambda m: (m["ep"], m["start"]))
            p = Promo(id=f"MONTAGE-{i+1}", kind="montage", title=mp.title, hook=mp.hook, cliffhanger=mp.cliffhanger,
                      why=mp.why, spoiler_risk=mp.spoiler_risk, model=model,
                      segments=[Segment(ep=m["ep"], start=m["start"], end=m["end"], start_beat=m["start_beat"],
                                        end_beat=m["end_beat"]) for m in ms],
                      scores={"hook": mp.hook_score, "cliffhanger": mp.cliffhanger_score, "standalone": mp.standalone_score},
                      retrieved_patterns=[f"{m['id']} ({m['slot']}, ep {m['ep']}, retrieval score {m['score']})" for m in ms])
            for k in range(len(p.segments) - 1, -1, -1):   # too short: run a moment on to its next line end,
                if p.duration >= 20.0:                        # latest moment first (episode-final cliffs have none)
                    break
                seg = p.segments[k]
                nxt = p.segments[k + 1] if k + 1 < len(p.segments) else None
                sep = eps[seg.ep]
                for b in sep.beats:
                    if b.kind == "LINE" and b.end > seg.end:
                        new_e = snap_end(sep, b.end)
                        if nxt and nxt.ep == seg.ep and new_e > nxt.start:
                            break
                        p.fixes.append(f"extended moment {k + 1} {fmt(seg.end)} -> {fmt(new_e)} to reach 20 s")
                        seg.end = new_e
                        if p.duration >= 20.0:
                            break
            p.problems = check(p, eps)
            p.passed = not p.problems
            p.rules_score = rules_quality(p, eps)
            out.append(p)
        return {"promos": out, "log": log}

    def to_viewers(s: ShowState):
        if R.viewer is None:
            return "rank"
        return [Send("viewer", {"promo": p, "clip": clip_text(p, {e.num: e for e in s["episodes"]})})
                for p in s["promos"]] or "rank"

    def viewer(s: dict) -> dict:
        p: Promo = s["promo"]
        try:
            v, _ = R.viewer.structured(BlindVerdict, prompts.VIEWER_SYSTEM,
                                       prompts.VIEWER_USER.format(seconds=p.duration, clip=s["clip"]))
            print(f"  viewer {p.id}: stop {v.stop_scrolling} next {v.want_next} understood {v.understood}", flush=True)
            return {"verdicts": {p.id: v}}
        except Exception as e:
            return {"log": [{"promo": p.id, "stage": "viewer", "error": str(e)[:300]}]}

    def rank(s: ShowState) -> dict:
        verdicts = s.get("verdicts", {})
        vals = list(verdicts.values())
        mean_blind = (sum(v.stop_scrolling + v.want_next + v.understood for v in vals) / (30 * len(vals))) if vals else None
        promos = []
        for p in s["promos"]:
            p.blind = verdicts.get(p.id)
            p.final_score = score(p, mean_blind)
            promos.append(p)
        promos.sort(key=lambda p: -p.final_score)
        for i, p in enumerate(promos, 1):
            p.rank = i
        return {"ranked": promos}

    def review(s: ShowState) -> dict:
        top = [{"rank": p.rank, "id": p.id, "segments": " + ".join(f"E{g.ep} {fmt(g.start)}-{fmt(g.end)}" for g in p.segments),
                "hook": p.hook, "cliffhanger": p.cliffhanger} for p in s["ranked"][:10]]
        decision = interrupt({"question": "Approve promos to post (ids)?", "top": top})
        approved = [x for x in (decision or {}).get("approve", []) if any(p.id == x for p in s["ranked"])]
        with open(KB / "approved_promos.jsonl", "a", encoding="utf-8") as f:
            for p in s["ranked"]:
                if p.id in approved:
                    f.write(json.dumps({"show": R.show, "title": p.title, "hook": p.hook,
                                        "cliffhanger": p.cliffhanger, "why": p.why}, ensure_ascii=False) + "\n")
        return {"approved": approved}

    g = StateGraph(ShowState)
    for name, fn in (("load", load), ("index", index), ("episode", episode), ("montage", montage),
                     ("viewer", viewer), ("rank", rank), ("review", review)):
        g.add_node(name, fn)
    g.add_edge(START, "load")
    g.add_edge("load", "index")
    g.add_conditional_edges("index", fan_out, ["episode"])
    g.add_edge("episode", "montage")
    g.add_conditional_edges("montage", to_viewers, ["viewer", "rank"])
    g.add_edge("viewer", "rank")
    g.add_edge("rank", "review" if R.review else END)
    g.add_edge("review", END)
    saver = MemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=[
        ("promo_finder.parse", "Episode"), ("promo_finder.parse", "Beat"), ("promo_finder.parse", "Scene"),
        ("promo_finder.schemas", "Promo"), ("promo_finder.schemas", "Segment"), ("promo_finder.schemas", "BlindVerdict")]))
    return g.compile(checkpointer=saver if R.review else None)


def score(p: Promo, mean_blind: float | None = None) -> float:
    """45% picker scores + 40% blind viewer + 15% rules; spoiler penalty; early-episode funnel bonus."""
    sc = p.scores
    model = (0.35 * sc.get("hook", 0) + 0.35 * sc.get("cliffhanger", 0) + 0.30 * sc.get("standalone", 0)) / 10 if sc else p.rules_score
    if p.blind:
        b = p.blind
        s = 0.45 * model + 0.40 * (b.stop_scrolling + b.want_next + b.understood) / 30 + 0.15 * p.rules_score
    elif mean_blind is not None:                  # viewer check missing: impute the average, never a free pass
        s = 0.45 * model + 0.40 * mean_blind + 0.15 * p.rules_score
    else:
        s = 0.85 * model + 0.15 * p.rules_score
    s -= {"medium": 0.03, "high": 0.08}.get(p.spoiler_risk, 0.0)
    first = min(p.episodes)
    s += 0.03 if first <= 10 else (0.01 if first <= 25 else 0.0)
    if not p.passed:
        s -= 0.25
    return round(s, 4)
