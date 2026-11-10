"""Find promo clips in a microdrama screenplay pack.

  python run.py --input "data/<show folder>"                          # Groq free tier (key in .env)
  python run.py --input show.zip --rules-only                         # no model at all, free, < 1 s
  python run.py --input show/ --episodes 1-10 --no-montage --no-viewer
  python run.py --input show/ --picker groq:qwen/qwen3.8-27b          # swap the model with one string
  python run.py --input show/ --review                                # editor approves picks (human in the loop)
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from promo_finder import llm as llm_mod
from promo_finder.graph import Resources, build_graph
from promo_finder.llm import LLM, enable_cache, load_env
from promo_finder.rag import PlaybookIndex
from promo_finder.report import seg_str, write_outputs


def resolve_input(path: str) -> Path:
    p = Path(path)
    if p.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="promo_"))
        with zipfile.ZipFile(p) as z:
            z.extractall(tmp)
        txts = list(tmp.rglob("*.txt"))
        if not txts:
            sys.exit("zip contains no .txt screenplays")
        return txts[0].parent
    if p.is_dir() and not list(p.glob("*.txt")):
        subs = [d for d in p.iterdir() if d.is_dir() and list(d.glob("*.txt"))]
        if len(subs) == 1:
            return subs[0]
    return p


def parse_eps(spec: str | None) -> list[int] | None:
    if not spec:
        return None
    keep: set[int] = set()
    for part in spec.split(","):
        a, _, b = part.partition("-")
        keep.update(range(int(a), int(b or a) + 1))
    return sorted(keep)


def run(input_path: str, show: str | None = None, picker: str = "groq:openai/gpt-oss-120b",
        viewer: str = "groq:qwen/qwen3.8-27b", fallback: str | None = "groq:openai/gpt-oss-20b",
        episodes: str | None = None, rules_only: bool = False, montage: bool = True, use_viewer: bool = True,
        playbook: bool = True, review: bool = False, workers: int = 4, out: str | None = None, quiet: bool = False):
    load_env()
    enable_cache()
    folder = resolve_input(input_path)
    show = show or folder.name
    R = Resources(show=show,
                  picker=None if rules_only else LLM(picker, max_tokens=1800, fallback=fallback),
                  viewer=None if rules_only or not use_viewer else LLM(viewer, max_tokens=600, otpm=950, expected_out=320),
                  playbook=None if rules_only or not playbook else PlaybookIndex(),
                  montage=montage and not rules_only, review=review)
    graph = build_graph(R)
    label = "rules-only" if rules_only else picker.split(":", 1)[1].split("/")[-1] + ("" if playbook else "-noplaybook")
    out_dir = Path(out or f"outputs/{label}")
    cfg = {"max_concurrency": workers, "recursion_limit": 200, "configurable": {"thread_id": "run"}}
    t0 = time.time()
    state = graph.invoke({"folder": str(folder), "only": parse_eps(episodes)}, cfg)
    if review and "__interrupt__" in state:                  # human-in-the-loop: editor approves picks
        from langgraph.types import Command
        print("\nTop picks for review:")
        for t in state["__interrupt__"][0].value["top"]:
            print(f"  #{t['rank']:<2} {t['id']:<12} {t['segments']}\n       hook: {t['hook'][:90]}")
        ids = input("Promo IDs to approve (comma-separated, blank for none): ").strip()
        state = graph.invoke(Command(resume={"approve": [x.strip() for x in ids.split(",") if x.strip()]}), cfg)
        print(f"approved {state.get('approved')} -> added to kb/approved_promos.jsonl")
    promos = state["ranked"]
    meta = {"show": show, "picker": "rules" if rules_only else picker, "fallback": None if rules_only else fallback,
            "viewer": None if (rules_only or not use_viewer) else viewer, "playbook_rag": playbook and not rules_only,
            "episodes": len(state["episodes"]), "beats": sum(len(e.beats) for e in state["episodes"]),
            "seconds": round(time.time() - t0, 1), "usage": llm_mod.USAGE, "input": str(folder)}
    write_outputs(out_dir, show, promos, state.get("log", []), meta)
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if not quiet:
        passed = sum(p.passed for p in promos)
        print(f"{show}: {meta['episodes']} episodes -> {len(promos)} promos ({passed} pass all checks) "
              f"in {meta['seconds']} s -> {out_dir}")
        for spec, u in llm_mod.USAGE.items():
            print(f"  {spec}: {u['calls']} calls, {u['input_tokens']} in / {u['output_tokens']} out tokens, {u['cache_hits']} cache hits")
        for p in promos[:10]:
            print(f"  #{p.rank:<2} {p.id:<12} {p.duration:5.1f}s  {seg_str(p)}  | {p.hook[:60]}")
    return promos, meta


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="folder of episode .txt files, or a .zip of them")
    ap.add_argument("--show", help="show title (default: folder name)")
    ap.add_argument("--picker", default="groq:openai/gpt-oss-120b", help="provider:model that picks promos")
    ap.add_argument("--fallback", default="groq:openai/gpt-oss-20b", help="used if the picker's daily quota runs out")
    ap.add_argument("--viewer", default="groq:qwen/qwen3.8-27b", help="provider:model for the blind viewer check")
    ap.add_argument("--episodes", help="e.g. 1-10 or 1,3,5-7")
    ap.add_argument("--rules-only", action="store_true", help="no model: keyword rules only")
    ap.add_argument("--no-montage", action="store_true")
    ap.add_argument("--no-viewer", action="store_true")
    ap.add_argument("--no-playbook", action="store_true", help="disable playbook RAG (for ablation)")
    ap.add_argument("--review", action="store_true", help="pause for an editor to approve picks")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out")
    a = ap.parse_args()
    run(a.input, a.show, a.picker, a.viewer, a.fallback, a.episodes, a.rules_only, not a.no_montage,
        not a.no_viewer, not a.no_playbook, a.review, a.workers, a.out)


if __name__ == "__main__":
    main()
