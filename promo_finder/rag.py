"""Retrieval-Augmented Generation: two FAISS indexes with FastEmbed embeddings.

1. PlaybookIndex: promo patterns (kb/playbook.json) plus editor-approved promos
   (kb/approved_promos.jsonl). For each episode the picker retrieves the most relevant
   patterns and gets them as grounding in its prompt. It grows with every approval.

2. MomentIndex: every ~8-15 s moment of the whole show, with metadata (episode, times,
   beat IDs, rule-based hook/cliff strength). The montage stage needs moments from
   *across* 50 episodes, which is ~45k tokens of script and too big for an 8K tokens/min
   free-tier budget. So it does hybrid retrieval:
       vector similarity  +  metadata filters (episode range for spoiler control, min cliff strength)
       -> re-rank with rule scores -> de-duplicate overlaps -> one moment per episode (diversity)
   and sends only ~10 moments to the model.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from .heuristics import cliff_strength, hook_strength, snap_end, snap_start
from .llm import CACHE
from .parse import Episode

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "kb"
INDEX_DIR = CACHE / "faiss"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
_EMB = None


def embeddings() -> FastEmbedEmbeddings:
    global _EMB
    if _EMB is None:
        _EMB = FastEmbedEmbeddings(model_name=EMBED_MODEL, cache_dir=str(CACHE / "fastembed"))
    return _EMB


def _sim(distance: float) -> float:
    """FAISS returns squared L2 distance; bge vectors are unit-normalised, so cos = 1 - d/2."""
    return max(0.0, min(1.0, 1.0 - distance / 2.0))


# ----------------------------------------------------------------- playbook
class PlaybookIndex:
    def __init__(self, extra_examples: bool = True):
        data = json.loads((KB / "playbook.json").read_text(encoding="utf-8"))
        docs = [Document(page_content=f"{p['name']}. Hook: {p['hook']} Cliffhanger: {p['cliffhanger']} Why: {p['why']}",
                         metadata={"type": "pattern", "name": p["name"], "stage": p["stage"]})
                for p in data["patterns"]]
        approved = KB / "approved_promos.jsonl"
        if extra_examples and approved.exists():
            for line in approved.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    a = json.loads(line)
                    docs.append(Document(
                        page_content=f"Approved promo ({a.get('show', '')}): hook: {a['hook']} | cuts on: {a['cliffhanger']} | why: {a['why']}",
                        metadata={"type": "approved", "name": f"approved: {a.get('title', '')}", "stage": "example"}))
        self.patterns = data["patterns"]
        self.store = FAISS.from_documents(docs, embeddings())

    def retrieve(self, query: str, k: int = 3) -> list[Document]:
        # MMR keeps the k patterns diverse instead of three near-duplicates
        return self.store.max_marginal_relevance_search(query, k=k, fetch_k=min(10, len(self.store.index_to_docstore_id)))

    def query_for_slot(self, stage: str) -> list[str]:
        return [p["query"] for p in self.patterns if p["stage"] == stage]


# ----------------------------------------------------------------- moments of the show
def build_moments(ep: Episode, min_len: float = 8.0, max_len: float = 15.0) -> list[dict]:
    beats = [b for b in ep.beats if b.kind != "CAMERA"]
    lines = [b for b in beats if b.kind == "LINE"]
    out = []
    for i, sb in enumerate(beats):
        if sb.kind not in ("LINE", "ACTION"):
            continue
        s = snap_start(ep, sb.start, slack=0.6)
        end_line = None
        for lb in lines:
            if lb.start >= sb.start and lb.end - s >= min_len:
                end_line = lb
                break
        if end_line is None or end_line.end - s > max_len:
            continue
        e = snap_end(ep, end_line.end)
        inside = [b for b in beats if s <= b.start < e]
        hook = max((hook_strength(b) for b in inside if b.start - s <= 3.0), default=0.0)
        cliff = max((cliff_strength(b, ep.duration) for b in inside if e - b.end <= 4.0), default=0.0)
        out.append({"ep": ep.num, "start": s, "end": e, "start_beat": sb.id, "end_beat": end_line.id,
                    "hook": round(hook, 3), "cliff": round(cliff, 3),
                    "text": " / ".join((f"{b.speaker}: {b.text}" if b.kind == "LINE" else f"({b.text[:90]})") for b in inside)})
    return out


class MomentIndex:
    def __init__(self, episodes: list[Episode]):
        self.moments = [m for ep in episodes for m in build_moments(ep)]
        # the episode logline gives each moment story-level meaning ("duchess recognises the family ring")
        # that raw dialogue lacks; the rule scores then pick the best moment inside the episode
        self.loglines = {ep.num: ep.logline for ep in episodes}
        key = hashlib.sha256(json.dumps([(m["ep"], m["start"], m["text"], self.loglines[m["ep"]])
                                         for m in self.moments]).encode()).hexdigest()[:16]
        path = INDEX_DIR / key
        if path.exists():
            self.store = FAISS.load_local(str(path), embeddings(), allow_dangerous_deserialization=True)
        else:
            docs = [Document(page_content=self.loglines[m["ep"]] + " Moment: " + m["text"], metadata={**{k: v for k, v in m.items() if k != "text"}, "i": i})
                    for i, m in enumerate(self.moments)]
            self.store = FAISS.from_documents(docs, embeddings())
            path.parent.mkdir(parents=True, exist_ok=True)
            self.store.save_local(str(path))

    def search(self, query: str, k: int = 3, max_ep: int | None = None, min_ep: int | None = None,
               min_cliff: float = 0.0, min_hook: float = 0.0, rule_key: str | None = None,
               exclude_eps: set[int] | None = None) -> list[dict]:
        def keep(md: dict) -> bool:                                   # structured metadata filter
            return ((max_ep is None or md["ep"] <= max_ep) and (min_ep is None or md["ep"] >= min_ep)
                    and md["cliff"] >= min_cliff and md["hook"] >= min_hook
                    and not (exclude_eps and md["ep"] in exclude_eps))
        hits = self.store.similarity_search_with_score(query, k=150, fetch_k=1700, filter=keep)
        ranked = []
        for doc, dist in hits:                                         # re-rank: semantic + rule signal
            md = doc.metadata
            rule = md[rule_key] if rule_key else (md["hook"] + md["cliff"]) / 2
            ranked.append((0.6 * _sim(dist) + 0.4 * rule, self.moments[md["i"]] | {"sim": round(_sim(dist), 3)}))
        ranked.sort(key=lambda x: -x[0])
        out, seen_eps = [], set()
        for score, m in ranked:                                        # de-dup + one per episode (diversity)
            if m["ep"] in seen_eps:
                continue
            seen_eps.add(m["ep"])
            out.append(m | {"score": round(score, 3)})
            if len(out) >= k:
                break
        return out
