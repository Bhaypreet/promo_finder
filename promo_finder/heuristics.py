"""Rule-based scoring (no AI). Two jobs:

1. Generate candidate windows for every episode cheaply, so the LLM gets good
   suggestions and the tool still produces output with NO model at all.
2. Provide an independent second opinion that the final ranking blends in.

All the word lists are plain, editable data — an editor can tune them without
touching code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .parse import Beat, Episode

MIN_LEN, MAX_LEN = 20.0, 60.0
HOOK_WINDOW = 3.0

# Physical / visual events that stop a scroll (ACTION / CAMERA / SFX text)
PHYSICAL = r"slap|strik|struck|punch|shov|grab|seiz|yank|kneel|knee|kiss|explo|blood|bleed|fire|flame|blaze|ablaze|inferno|crash|shatter|collaps|sword|blade|dagger|knife|chain|shackle|whip|riding crop|burst|slam|drag|throws?|hurl|choke|faint|scream|thrust|torch|hot iron|noose|gallows|gavel|rip|tear[s]? (?:the|her|his)|unmask|reveal|regalia|crest|signet|ring"
# Emotionally loaded tones in the speaker tag, e.g. "(Furious)"
HOT_TONES = r"furi|rage|enrag|scream|shout|yell|roar|outrag|threat|menac|venom|cruel|vicious|sadist|gloat|smug|mock|sneer|cold|icy|lethal|deadly|shock|horrif|stunned|desperat|sob|gasp|beg|plead|defian|accus|command|bark|hiss|seeth|disgust|contempt|triumph|broken|devastat|terrif|panic"
# Loaded words in dialogue
HOT_WORDS = r"\bkill|\bdie\b|\bdead\b|death|hang|gallows|execut|poison|arsenic|witch|burn|traitor|treason|liar|murder|betray|marry|married|wedding|husband|wife|duke|duchess|worthless|nothing|disown|inherit|prison|dungeon|arrest|thief|steal|stole|blood|son\b|mother|alive|truth|secret|never|swear|beg|kneel|slap|disgrace|shame|beggar|peasant|cripple|scar"
# What makes an ending feel unresolved
CLIFF_WORDS = r"\bor\b|unless|\bif you\b|will (?:hang|burn|die|pay|regret)|by dawn|tomorrow|tonight|before|who are you|what are you|the truth|your name|identity|alive|my son|is the duke|wait|stop|don'?t|how dare|you will|i will|you'll|i'll"
CLIFF_FX = r"cliffhanger|ominous|swell|sting|drone|cut to black|freeze|silence|heartbeat|thunder|gasp"
CLIFF_ACTION = r"door (?:burst|bang|slam|open|crash)|turns?|eyes? widen|freez|stunned|frozen|look(?:s)? up|silhouett|enters|appears|reveal|cut to black|reach(?:es)? for|draws? (?:a|his|her) (?:sword|blade|dagger)"
DEPENDENT_OPENERS = r"^(and|but|so|then|he|she|it|that|this|they|them|his|her|yes|no|because|which|also|still|again)\b"


def _count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, flags=re.I))


def hook_strength(b: Beat) -> float:
    t = b.text or ""
    if b.kind == "LINE":
        s = 0.2
        s += 0.3 * min(1, _count(HOT_TONES, b.tone or ""))
        s += 0.15 * min(2, _count(HOT_WORDS, t))
        s += 0.1 if "!" in t else 0.0
        s += 0.1 if re.match(r"^\W*you\b", t, re.I) else 0.0
        s += 0.1 if len(t.split()) <= 8 else 0.0
        return min(s, 1.0)
    if b.kind in ("ACTION", "CAMERA"):
        return min(1.0, 0.1 + 0.3 * min(3, _count(PHYSICAL, t)))
    if b.kind == "SOUND":
        return min(1.0, 0.1 + 0.3 * min(2, _count(r"explo|crack|slam|scream|crash|shatter|bang|smash", t)))
    return 0.0


def cliff_strength(b: Beat, ep_duration: float) -> float:
    t = b.text or ""
    s = 0.0
    if b.kind == "LINE":
        s += 0.3 if t.rstrip().endswith("?") else 0.0
        s += 0.15 * min(2, _count(CLIFF_WORDS, t))
        s += 0.2 * min(1, _count(r"ominous|threat|menac|cold|icy|lethal|shock|stunned|horrif|defian|vow", b.tone or ""))
        s += 0.1 if t.rstrip().endswith(("...", "…", "—", "-")) else 0.0
    elif b.kind == "SOUND":
        s += 0.4 * min(1, _count(CLIFF_FX, t))
    else:
        s += 0.25 * min(2, _count(CLIFF_ACTION, t))
    if ep_duration - b.end <= 6.0:          # writers already end every episode on a cliffhanger
        s += 0.3
    return min(s, 1.0)


def snap_start(ep: Episode, t: float, slack: float = 1.0) -> float:
    """Move a start time back to the nearest shot cut if one is within `slack` seconds."""
    best = t
    for c in ep.cuts():
        if t - slack <= c <= t + 1e-6:
            best = c
    if best == t:
        best = max(0.0, t - 0.2)
    return round(best, 2)


def snap_end(ep: Episode, t: float, slack: float = 1.5) -> float:
    """Move an end time forward to the nearest shot cut if one is within `slack` seconds."""
    for c in ep.cuts():
        if t - 1e-6 <= c <= t + slack:
            return round(c, 2)
    return round(min(ep.duration, t + 0.3), 2)


@dataclass
class Window:
    ep: int
    start: float
    end: float
    start_beat: str
    end_beat: str
    hook: float
    cliff: float
    heat: float
    standalone: float
    score: float
    hook_text: str = ""
    cliff_text: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start


def _standalone(ep: Episode, start: float, end: float, first: Beat) -> tuple[float, list[str]]:
    s, notes = 1.0, []
    lines = [b for b in ep.beats if b.kind == "LINE" and start <= b.start < end]
    if lines and re.match(DEPENDENT_OPENERS, lines[0].text.strip().strip('"'), re.I):
        s -= 0.25; notes.append("opens on a dependent line")
    prev = [b for b in ep.beats if b.kind == "LINE" and start - 1.5 <= b.end <= start]
    if prev and prev[-1].text.rstrip().endswith("?"):
        s -= 0.25; notes.append("starts on an answer to an unseen question")
    scenes = {b.scene for b in ep.beats if start <= b.start < end}
    if len(scenes) > 1:
        s -= 0.15 * (len(scenes) - 1); notes.append(f"spans {len(scenes)} scenes")
    if any(abs(sc.start - start) < 1.0 for sc in ep.scenes):
        s += 0.1
    if not lines:
        s -= 0.3; notes.append("no dialogue")
    return max(0.0, min(1.0, s)), notes


def candidate_windows(ep: Episode, top_k: int = 4) -> list[Window]:
    beats = [b for b in ep.beats if b.kind != "CAMERA"]
    dur = ep.duration
    hooks = {b.id: hook_strength(b) for b in ep.beats}
    cliffs = {b.id: cliff_strength(b, dur) for b in ep.beats}

    starts = [b for b in beats if hooks[b.id] >= 0.45] or sorted(beats, key=lambda b: -hooks[b.id])[:8]
    out: list[Window] = []
    for sb in starts:
        s = snap_start(ep, sb.start)
        hook_beats = [b for b in ep.beats if s <= b.start <= s + HOOK_WINDOW]
        hook = max((hooks[b.id] for b in hook_beats), default=0.0)
        for eb in beats:
            if eb.end <= sb.start:
                continue
            e = snap_end(ep, eb.end)
            # never cut through a line of dialogue
            cut_lines = [b for b in ep.beats if b.kind == "LINE" and b.start < e < b.end]
            if cut_lines:
                e = snap_end(ep, max(b.end for b in cut_lines))
            d = e - s
            if d < MIN_LEN or d > MAX_LEN:
                continue
            tail = [b for b in ep.beats if e - 4.0 <= b.end <= e + 0.01]
            cliff = max((cliffs[b.id] for b in tail), default=0.0)
            inside = [b for b in ep.beats if s <= b.start < e and b.kind != "CAMERA"]
            heat = sum(hooks[b.id] for b in inside) / max(1, len(inside))
            stand, notes = _standalone(ep, s, e, sb)
            sweet = 1.0 if 30 <= d <= 50 else 0.85
            score = (0.35 * hook + 0.35 * cliff + 0.15 * heat + 0.15 * stand) * sweet
            hb = max(hook_beats, key=lambda b: hooks[b.id]) if hook_beats else sb
            cb = max(tail, key=lambda b: cliffs[b.id]) if tail else eb
            out.append(Window(ep.num, s, e, sb.id, eb.id, round(hook, 3), round(cliff, 3),
                              round(heat, 3), round(stand, 3), round(score, 4),
                              hook_text=hb.text, cliff_text=cb.text, notes=notes))
    # greedy non-max suppression: keep diverse, non-overlapping windows
    out.sort(key=lambda w: -w.score)
    kept: list[Window] = []
    for w in out:
        if all(_iou(w, k) < 0.25 for k in kept):
            kept.append(w)
        if len(kept) >= top_k:
            break
    return kept


def _iou(a: Window, b: Window) -> float:
    inter = max(0.0, min(a.end, b.end) - max(a.start, b.start))
    union = max(a.end, b.end) - min(a.start, b.start)
    return inter / union if union else 0.0


def beat_scores(ep: Episode) -> dict[str, tuple[float, float]]:
    return {b.id: (hook_strength(b), cliff_strength(b, ep.duration)) for b in ep.beats}
