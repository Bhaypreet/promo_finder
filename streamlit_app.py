"""Hosted demo of Promo Finder (Streamlit Community Cloud). Same LangGraph pipeline as run.py and app.py.

    streamlit run streamlit_app.py
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
try:                                              # hosted file systems can be read-only outside /tmp
    (ROOT / ".cache").mkdir(exist_ok=True)
    (ROOT / ".cache" / ".w").touch()
except OSError:
    os.environ.setdefault("PROMO_CACHE_DIR", str(Path(tempfile.gettempdir()) / "promo_cache"))
try:                                              # Streamlit secrets -> env, so the pipeline sees the key
    for name in ("GROQ_API_KEY", "GROK_API_KEY"):  # accept the common misspelling too
        if name in st.secrets:
            os.environ.setdefault("GROQ_API_KEY", str(st.secrets[name]).strip())
            break
except Exception:
    pass

from promo_finder.llm import load_env  # noqa: E402
from run import run  # noqa: E402

load_env()
DEMO = ROOT / "samples" / "demo_show"
HAS_KEY = bool(os.environ.get("GROQ_API_KEY"))
REPO = "https://github.com/Bhaypreet/promo_finder"

st.set_page_config(page_title="Promo Finder", page_icon="🎬", layout="wide")


@st.cache_resource
def run_lock() -> threading.Lock:
    return threading.Lock()                       # one run at a time: the free-tier token budget is shared


def show_folder(upload) -> tuple[Path, str]:
    if upload is None:
        return DEMO, "Demo show (3 original episodes)"
    tmp = Path(tempfile.mkdtemp(prefix="upload_"))
    with zipfile.ZipFile(upload) as z:
        z.extractall(tmp)
    txts = sorted(tmp.rglob("*.txt"))
    if not txts:
        raise ValueError("The zip has no .txt screenplays in it.")
    return txts[0].parent, Path(upload.name).stem


def mmss(t: float) -> str:
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:05.2f}"


# ------------------------------------------------------------------ header
st.title("Promo Finder")
st.write("Reads microdrama screenplays and returns a ranked list of 20-60 s promos: for each one, the episode and "
         "start/end time of every segment, the hook in the first 3 seconds, the cliffhanger it cuts on, and why it works.")

with st.expander("How it works", expanded=False):
    st.markdown(
        "- **Parse** each screenplay into timestamped beats (code).\n"
        "- **Rule scorer** proposes candidate windows from keywords and tone tags (code).\n"
        "- **Retrieve** the 3 most relevant promo patterns from a playbook with FAISS + FastEmbed (RAG).\n"
        "- **Pick** promos with an LLM on Groq, which answers in beat IDs validated by Pydantic; code turns IDs into "
        "cut times on shot changes, never mid-line.\n"
        "- **Check and repair**: 20-60 s, hook in 3 s, ends on the cliffhanger; failures go back to the model once (LangGraph).\n"
        "- **Cold-viewer test**: a different model sees only the clip and scores stop / want-next / understood.\n"
        "- **Rank**: 45% picker + 40% cold viewer + 15% rules, minus spoiler risk, plus an early-episode bonus.\n\n"
        f"Code, FastAPI service and Dockerfile: [{REPO}]({REPO})")

# ------------------------------------------------------------------ inputs
left, right = st.columns([3, 2], gap="large")
with left:
    source = st.radio("Screenplays", ["Demo show (3 original episodes)", "Upload a .zip of episode .txt files"],
                      horizontal=True)
    upload = st.file_uploader("Zip of episode screenplays", type=["zip"]) if source.startswith("Upload") else None
    if source.startswith("Demo"):
        st.caption("A short original show written for this demo, in the same screenplay format as the input pack.")
with right:
    modes = ["AI pipeline (Groq LLMs + RAG)", "Rules only (no AI, instant)"]
    mode = st.radio("Mode", modes, index=0 if HAS_KEY else 1, disabled=not HAS_KEY)
    if not HAS_KEY:
        st.caption("No GROQ_API_KEY is configured on this deployment, so only rules-only mode is available.")
    episodes = st.text_input("Episodes (optional)", placeholder="e.g. 1-5 or 1,3,7",
                             help="Leave empty for all. The AI mode takes about a minute per episode on Groq's free tier.")
    c1, c2 = st.columns(2)
    use_viewer = c1.checkbox("Cold-viewer test", value=True, disabled=mode != modes[0])
    montage = c2.checkbox("Cross-episode montages", value=True, disabled=mode != modes[0])

go = st.button("Find promos", type="primary", disabled=source.startswith("Upload") and upload is None)

# ------------------------------------------------------------------ run
if go:
    rules_only = mode != modes[0]
    try:
        folder, show = show_folder(upload)
    except (zipfile.BadZipFile, ValueError) as e:
        st.error(f"Could not read the upload: {e}")
        st.stop()
    n_eps = len(list(folder.glob("*.txt")))
    if not rules_only and not episodes and n_eps > 10:
        st.warning(f"{n_eps} episodes in AI mode will take roughly {n_eps} minutes on the free tier. "
                   "Enter an episode range (e.g. 1-5) for a quicker run, or use rules-only mode.")
    out = Path(tempfile.mkdtemp(prefix="promos_"))
    lock = run_lock()
    with st.status("Finding promos...", expanded=True) as status:
        if lock.locked():
            st.write("Another run is in progress; waiting for it to finish.")
        with lock:
            st.write(f"{show}: {n_eps} episode files, mode: {'rules only' if rules_only else 'AI pipeline'}.")
            t0 = time.time()
            try:
                promos, meta = run(str(folder), show=show, episodes=episodes or None, rules_only=rules_only,
                                   montage=montage, use_viewer=use_viewer, out=str(out), quiet=True)
            except Exception as e:                                   # show the reason, keep the app alive
                status.update(label="Run failed", state="error")
                st.error(f"{type(e).__name__}: {str(e)[:400]}")
                st.stop()
            status.update(label=f"Done in {time.time() - t0:.1f} s", state="complete", expanded=False)
    st.session_state["result"] = {
        "show": show, "meta": meta,
        "promos": json.loads((out / "promos.json").read_text(encoding="utf-8"))["promos"],
        "csv": (out / "promos_cutlist.csv").read_bytes(),
        "json": (out / "promos.json").read_bytes(),
        "md": (out / "promos.md").read_bytes(),
    }

# ------------------------------------------------------------------ results
res = st.session_state.get("result")
if res:
    promos, meta = res["promos"], res["meta"]
    st.subheader(f"Ranked promos: {res['show']}")
    m = st.columns(4)
    m[0].metric("Promos", len(promos))
    m[1].metric("Pass every check", sum(p["passed"] for p in promos))
    m[2].metric("Episodes", meta["episodes"])
    m[3].metric("Picker", "rules" if meta["picker"] == "rules" else meta["picker"].split("/")[-1])

    rows = []
    for p in promos:
        b = p.get("blind") or {}
        rows.append({
            "Rank": p["rank"], "Promo": p["id"], "Kind": p["kind"],
            "Segments": " + ".join(f"Ep{s['ep']} {mmss(s['start'])}-{mmss(s['end'])}" for s in p["segments"]),
            "Sec": round(p["duration"], 1), "Hook (first 3 s)": p["hook"], "Cliffhanger": p["cliffhanger"],
            "Why it works": p["why"], "Score": round(p["final_score"], 3),
            "Viewer stop/next/understood": f"{b['stop_scrolling']}/{b['want_next']}/{b['understood']}" if b else "",
            "Checks": "pass" if p["passed"] else "; ".join(p["problems"]),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    d = st.columns(3)
    d[0].download_button("Download cut list (CSV)", res["csv"], "promos_cutlist.csv", "text/csv")
    d[1].download_button("Download report (Markdown)", res["md"], "promos.md", "text/markdown")
    d[2].download_button("Download everything (JSON)", res["json"], "promos.json", "application/json")

    st.markdown("#### Details")
    for p in promos[:10]:
        with st.expander(f"#{p['rank']}  {p['title']}  ({p['duration']:.0f} s)"):
            for s in p["segments"]:
                st.markdown(f"- **Episode {s['ep']}**, {mmss(s['start'])} to {mmss(s['end'])} "
                            f"(beats {s['start_beat']} to {s['end_beat']})")
            st.markdown(f"**Hook:** {p['hook']}  \n**Cliffhanger:** {p['cliffhanger']}  \n**Why:** {p['why']}")
            if p.get("retrieved_patterns"):
                st.caption("Retrieved playbook patterns: " + ", ".join(p["retrieved_patterns"]))
            if p.get("blind"):
                b = p["blind"]
                st.markdown(f"**Cold viewer** ({b['stop_scrolling']}/{b['want_next']}/{b['understood']}): "
                            f"{b['what_is_happening']}")
            if p["fixes"]:
                st.caption("Fixes: " + "; ".join(p["fixes"]))
            if not p["passed"]:
                st.warning("Fails: " + "; ".join(p["problems"]))
