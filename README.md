# Promo Finder: microdrama screenplay → ranked promo cut list

Kuku AI Generalist Assignment, **Problem 1: Find the Promos**.

**Live demo:** https://promo-finder-demo.streamlit.app. It runs on an original 3-episode demo show, or you can upload
a .zip of episode screenplays. AI mode needs `GROQ_API_KEY` in the app's secrets; without it, the app runs rules-only.

Reads a folder (or .zip) of timestamped episode screenplays and returns ranked 20–60 s promos. Each promo
comes with the episode and start/end timestamps of every segment, the hook, the cliffhanger, a one-line
"why", and QA results.

**Stack:** Python · LangGraph (orchestration, conditional routing, parallel fan-out, human-in-the-loop) ·
LangChain (model-agnostic chat models, structured output, SQLite cache) · RAG with FAISS + FastEmbed (hybrid retrieval) ·
Pydantic (validated LLM outputs) · Groq (free-tier LLMs) · Pandas · FastAPI · Docker.

## Run it

```bash
python -m venv .venv && .venv\Scripts\activate        # (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
echo GROQ_API_KEY=gsk_... > .env                      # free key from console.groq.com

python run.py --input "path/to/show.zip"                       # full pipeline on Groq
python run.py --input "path/to/show_folder" --rules-only       # no model, free, < 1 s
python run.py --input show/ --episodes 1-10 --no-montage --no-viewer
python run.py --input show/ --picker groq:qwen/qwen3.8-27b     # swap the model with one string
python run.py --input show/ --review                           # editor approves picks; approvals feed the RAG playbook

python eval/evaluate.py outputs/rules-only outputs/gpt-oss-120b   # score runs against hand-picked reference promos

streamlit run streamlit_app.py                                 # the web demo, locally
python samples/make_demo_show.py                               # regenerate the original demo show in samples/

uvicorn app:app --port 7860                                    # REST API, docs at http://localhost:7860/docs
docker build -t promo-finder . && docker run -p 7860:7860 -e GROQ_API_KEY=... promo-finder
```

Any provider LangChain's `init_chat_model` supports works as `provider:model`
(e.g. `openai:gpt-4.1-mini`, `huggingface:<model-id>`, or Kuku's own OpenAI-compatible gateway) once its integration package and API key are installed.

Outputs land in `outputs/<model>/`:

| file | for whom | what |
|---|---|---|
| `promos_cutlist.csv` | editor | one row per segment: rank, episode, start, end, beat IDs, hook, cliffhanger, why, QA scores |
| `promos.md` | reviewer | ranked table + per-promo details, retrieved patterns, blind-viewer reaction, fixes, failed checks |
| `promos.json` | machines | everything, plus the validation / repair / retrieval log |
| `run_meta.json` | ops | models, token usage per model, runtime |

All LLM responses are cached in `.cache/llm_cache.sqlite` (LangChain SQLiteCache). A rerun spends no tokens and
gives identical output; delete the file to resample.

## How it works

```
LangGraph:  load ─► index ─► [Send × episodes] episode sub-graph ─► montage ─► [Send × promos] blind viewer ─► rank ─► (review) ─► END

episode sub-graph:  retrieve_patterns (RAG) ─► pick (LLM → Pydantic EpisodePicks) ─► check (code)
                                                        ▲                                │ rule broken?
                                                        └────────── repair (LLM) ◄───────┘ (max 1 round)
```

| step | who | what |
|---|---|---|
| parse | code | each `.txt` → Pydantic `Episode` of ~75 beats with IDs (`B031`), times and shot cuts |
| rules | code | keyword scorer for hook / cliffhanger / standalone → candidate windows; also the free fallback mode |
| retrieve_patterns | RAG | FAISS + FastEmbed over `kb/playbook.json` (16 promo patterns) + `kb/approved_promos.jsonl`, MMR top-3 |
| pick | LLM | Groq `gpt-oss-120b` reads the episode transcript + patterns + rule hints → promos as **beat IDs**, validated by Pydantic |
| check / repair | code + LLM | beat IDs → timestamps snapped to shot cuts, never mid-line; 20–60 s, hook ≤ 3 s, ends on the cliffhanger; auto-fix, else one LLM repair |
| montage | RAG + LLM | hybrid retrieval over 1,640 moments of the whole show (vector similarity + metadata filters + rule re-rank + de-dup + one-per-episode diversity) → LLM stitches cross-episode promos |
| blind viewer | LLM | a *different* model (Groq `qwen3.8-27b`) sees only the clip text, no show context, and rates stop / want-next / understood |
| rank | code | 45% picker scores + 40% blind viewer + 15% rules − spoiler penalty + early-episode bonus |
| review | human | optional LangGraph `interrupt()`; approved promos go into the knowledge base used by future runs |

Free-tier engineering: Groq allows ~8K tokens/min per model, so prompts drop camera beats (~900 tokens per
episode), a token-budget limiter paces parallel calls, the picker falls back to `gpt-oss-20b` if its daily quota
runs out, and the viewer runs on a different model with its own quota.

## Input format assumed

`EPISODE LOGLINE`, `SCENE NN` blocks with `Scene start/end`, then `**CAMERA:** / **ACTION:** / **SOUND FX:** /
**SPEAKER (Tone):**` headers, each followed by `Start: (MM:SS.ss) | End: (MM:SS.ss)` and text. The episode number
comes from the file name (`episode-007-...`).

The input pack is Kuku-confidential and is **not** in this repo (`data/` and `*.zip` are git-ignored).
