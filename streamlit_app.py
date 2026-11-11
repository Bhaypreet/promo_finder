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
    if "GROQ_API_KEY" in st.secrets:
        os.environ.setdefault("GROQ_API_KEY", str(st.secrets["GROQ_API_KEY"]).strip())
except Exception:
    pass

from promo_finder.llm import check_key, load_env  # noqa: E402
from run import run  # noqa: E402

load_env()
DEMO = ROOT / "samples" / "demo_show"
HAS_KEY = bool(os.environ.get("GROQ_API_KEY"))
REPO = "https://github.com/Bhaypreet/promo_finder"
# label -> (kind, default picker, default cold viewer, default tokens/min)
PROVIDERS = {
    "OpenAI-compatible endpoint (custom base URL)": ("compat", "", "", 100000),
    "Groq": ("groq", "openai/gpt-oss-120b", "qwen/qwen3.8-27b", 7800),
    "OpenAI": ("openai", "gpt-4.1-mini", "gpt-4.1-nano", 200000),
}


def own_spec(provider: str, model: str) -> str:
    """LangChain provider:model string. Custom gateways speak the OpenAI protocol."""
    return ("groq:" if PROVIDERS[provider][0] == "groq" else "openai:") + model

st.set_page_config(page_title="Promo Finder", page_icon="🎬", layout="wide")


STALE_AFTER = 12 * 60                             # an AI run never legitimately takes this long on the demo


@st.cache_resource
def run_slot() -> dict:
    """One AI run at a time (the free-tier token budget is shared by every visitor).

    The old version waited on a plain lock. If a visitor refreshed the page mid-run, Streamlit could not stop the
    thread stuck inside the pipeline, so the lock stayed held and every later visitor saw "Another run is in
    progress" forever. Now: nobody ever waits blindly, rules-only mode skips the slot, and a slot older than
    STALE_AFTER is taken over.
    """
    return {"guard": threading.Lock(), "since": None}


def claim_slot() -> float | None:
    """Returns None if claimed, else how many seconds the current run has been going."""
    slot = run_slot()
    with slot["guard"]:
        now = time.time()
        if slot["since"] is not None and now - slot["since"] < STALE_AFTER:
            return now - slot["since"]
        slot["since"] = now
        return None


def free_slot() -> None:
    slot = run_slot()
    with slot["guard"]:
        slot["since"] = None


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
    mode_box = st.container()                     # filled below, once we know whether a key was pasted
    with st.expander("Use your own API key (e.g. Kuku's own models)", expanded=False):
        provider = st.selectbox("Provider", list(PROVIDERS))
        own_key = st.text_input("API key", type="password", key="own_key",
                                help="Used only for runs in this browser tab. Never saved, logged or cached.").strip()
        own_url = st.text_input("Base URL", placeholder="https://<your-gateway>/v1",
                                help="The OpenAI-compatible endpoint of your API.").strip() \
            if PROVIDERS[provider][0] == "compat" else ""
        d_pick, d_view, d_tpm = PROVIDERS[provider][1:]
        pick_model = st.text_input("Picker model", value=d_pick, key=f"pick_{provider}").strip()
        view_model = st.text_input("Cold-viewer model", value=d_view, key=f"view_{provider}",
                                   help="Ideally a different model from the picker, so it judges the clip fresh.").strip()
        own_tpm = int(st.number_input("Tokens-per-minute limit of this key", min_value=1000, value=d_tpm, step=1000,
                                      key=f"tpm_{provider}"))
        if st.button("Check key", disabled=not own_key or not pick_model):
            try:
                reply = check_key(own_spec(provider, pick_model), own_key, own_url or None)
                st.success(f"Key works. {pick_model} replied: {reply!r}")
            except Exception as e:
                st.error(f"Key check failed: {type(e).__name__}: {str(e)[:300]}")
        st.caption("With your own key, runs skip the shared free-tier queue and go as fast as the key allows.")
    use_own = bool(own_key and pick_model)
    can_ai = HAS_KEY or use_own
    with mode_box:
        modes = ["AI pipeline (LLMs + RAG)", "Rules only (no AI, instant)"]
        mode = st.radio("Mode", modes, index=0 if can_ai else 1, disabled=not can_ai)
        if use_own:
            st.caption(f"AI mode will use your key: {own_spec(provider, pick_model)}.")
        elif not HAS_KEY:
            st.caption("No GROQ_API_KEY is configured on this deployment. Paste a key below for AI mode, "
                       "or use rules-only mode.")
        else:
            st.caption("The AI pipeline takes about 4 minutes on the 3-episode demo: Groq's free tier allows ~8K tokens "
                       "a minute per model. Rules-only returns in about a second.")
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
    shared = not rules_only and not use_own        # only the deployment's own free-tier key is shared
    own = {}
    if not rules_only and use_own:
        own = {"picker": own_spec(provider, pick_model), "viewer": own_spec(provider, view_model or pick_model),
               "fallback": "groq:openai/gpt-oss-20b" if PROVIDERS[provider][0] == "groq" else None,
               "api_key": own_key, "base_url": own_url or None, "tpm": own_tpm}
    if shared:
        busy = claim_slot()
        if busy is not None:
            st.warning(f"Another visitor's AI run started {busy / 60:.1f} min ago and is using the shared free-tier "
                       "token budget. Try again in a few minutes, or pick **Rules only** for an instant result.")
            st.stop()
    with st.status("Finding promos...", expanded=True) as status:
        st.write(f"{show}: {n_eps} episode files, mode: {'rules only' if rules_only else 'AI pipeline'}.")
        t0 = time.time()
        try:
            promos, meta = run(str(folder), show=show, episodes=episodes or None, rules_only=rules_only,
                               montage=montage, use_viewer=use_viewer, out=str(out), quiet=True, **own)
        except Exception as e:                                       # show the reason, keep the app alive
            status.update(label="Run failed", state="error")
            msg = str(e).replace(own_key, "***") if own_key else str(e)
            st.error(f"{type(e).__name__}: {msg[:400]}")
            st.stop()
        finally:
            if shared:
                free_slot()
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
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

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
