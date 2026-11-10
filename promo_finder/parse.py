"""Screenplay parser: one episode .txt -> a Pydantic `Episode` of timestamped beats.

Pure code, no AI. The input format is very regular:

    SCENE 01
    Scene heading: INT. CATHEDRAL – DAY
    Scene start: 00:00.00
    Scene end: 02:18.00
    **CAMERA:**                     <- or ACTION / SOUND FX / SPEAKER (Tone)
    Start: (00:00.00) | End: (00:04.80)
    text...
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, PrivateAttr

HEADER_RE = re.compile(r"^\*\*(.+?):\*\*\s*$")
TIME_RE = re.compile(r"^Start:\s*\((\d+):(\d+(?:\.\d+)?)\)\s*\|\s*End:\s*\((\d+):(\d+(?:\.\d+)?)\)")
SCENE_RE = re.compile(r"^SCENE\s+(\d+)")
EP_NUM_RE = re.compile(r"episode-(\d+)", re.I)
NON_TONE = {"O.S.", "V.O.", "O.C.", "CONT'D", "CONT’D"}


def ts(mm: str, ss: str) -> float:
    return int(mm) * 60 + float(ss)


def fmt(t: float) -> str:
    """seconds -> MM:SS.ss (same style as the scripts)."""
    m, s = divmod(max(t, 0.0), 60)
    return f"{int(m):02d}:{s:05.2f}"


class Beat(BaseModel):
    id: str                       # "B012", unique within the episode
    ep: int
    idx: int
    scene: int
    kind: Literal["CAMERA", "ACTION", "SOUND", "LINE"]
    speaker: str | None = None
    tone: str | None = None
    start: float
    end: float
    text: str

    def render(self, max_action: int = 140) -> str:
        """One compact prompt line: `B012 41.2-43.0 CLARISSA (Cruel): text`."""
        if self.kind == "LINE":
            who = f"{self.speaker}" + (f" ({self.tone})" if self.tone else "")
            text = self.text
        else:
            who = {"CAMERA": "[CAM]", "ACTION": "[ACT]", "SOUND": "[SFX]"}[self.kind]
            text = self.text if len(self.text) <= max_action else self.text[:max_action].rsplit(" ", 1)[0] + "…"
        return f"{self.id} {self.start:.1f}-{self.end:.1f} {who}: {text}"


class Scene(BaseModel):
    num: int
    heading: str = ""
    start: float = 0.0
    end: float = 0.0


class Episode(BaseModel):
    num: int
    path: str
    logline: str = ""
    continuity: str = ""
    scenes: list[Scene] = []
    beats: list[Beat] = []
    _idx: dict | None = PrivateAttr(default=None)
    _cuts: list | None = PrivateAttr(default=None)

    @property
    def duration(self) -> float:
        ends = [s.end for s in self.scenes] + [b.end for b in self.beats]
        return max(ends) if ends else 0.0

    def beat(self, bid: str) -> Beat | None:
        if self._idx is None:
            self._idx = {b.id: b for b in self.beats}
        return self._idx.get(str(bid).split("-")[-1].strip().upper())

    def cuts(self) -> list[float]:
        """Shot boundaries (CAMERA starts/ends + scene bounds): where an editor can cut cleanly."""
        if self._cuts is None:
            pts = {0.0, round(self.duration, 2)}
            for b in self.beats:
                if b.kind == "CAMERA":
                    pts.update((round(b.start, 2), round(b.end, 2)))
            for s in self.scenes:
                pts.update((round(s.start, 2), round(s.end, 2)))
            self._cuts = sorted(pts)
        return self._cuts

    def transcript(self, start: float = 0.0, end: float | None = None, camera: bool = False) -> str:
        """Compact beat list for prompts. Camera beats are dropped by default: ACTION beats already
        describe what happens on screen, and leaving camera out halves the token count."""
        end = self.duration if end is None else end
        return "\n".join(b.render() for b in self.beats
                         if start - 1e-6 <= b.start < end and (camera or b.kind != "CAMERA"))


def _split_header(h: str) -> tuple[str, str | None, str | None]:
    h = h.strip()
    up = h.upper()
    if up == "CAMERA":
        return "CAMERA", None, None
    if up == "ACTION":
        return "ACTION", None, None
    if up.startswith("SOUND"):
        return "SOUND", None, None
    parens = re.findall(r"\(([^)]*)\)", h)
    speaker = re.sub(r"\s*\(.*$", "", h).strip()
    tones = [p for p in parens if p.strip().upper() not in NON_TONE]
    return "LINE", speaker, (tones[-1].strip() if tones else None)


def parse_episode(path: str | Path) -> Episode:
    path = Path(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    m = EP_NUM_RE.search(path.name)
    num = int(m.group(1)) if m else 0
    ep = Episode(num=num, path=str(path))

    cur: Scene | None = None
    header: tuple | None = None
    times: tuple[float, float] | None = None
    buf: list[str] = []

    def flush():
        nonlocal header, times, buf
        if header and times:
            kind, spk, tone = header
            text = " ".join(t.strip() for t in buf if t.strip()).strip()
            if kind == "LINE":
                text = text.strip('"').strip("“”").strip()
            i = len(ep.beats)
            ep.beats.append(Beat(id=f"B{i:03d}", ep=num, idx=i, scene=cur.num if cur else 0, kind=kind,
                                 speaker=spk, tone=tone, start=times[0], end=times[1], text=text))
        header, times, buf = None, None, []

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("EPISODE LOGLINE:"):
            ep.logline = line.split(":", 1)[1].strip(); continue
        if line.startswith("CONTINUITY NOTES:"):
            ep.continuity = line.split(":", 1)[1].strip(); continue
        if line.startswith("--- SCRIPT"):
            flush(); continue
        sm = SCENE_RE.match(line)
        if sm:
            flush()
            cur = Scene(num=int(sm.group(1)))
            ep.scenes.append(cur); continue
        if cur and line.startswith("Scene heading:"):
            cur.heading = line.split(":", 1)[1].strip(); continue
        if cur and line.startswith(("Scene start:", "Scene end:")):
            mm, ss = line.split(":", 1)[1].strip().split(":")
            setattr(cur, "start" if "start" in line else "end", ts(mm, ss)); continue
        if line.startswith("Actions and dialogue:"):
            continue
        hm = HEADER_RE.match(line)
        if hm:
            flush()
            header = _split_header(hm.group(1)); continue
        tm = TIME_RE.match(line)
        if tm and header:
            times = (ts(tm.group(1), tm.group(2)), ts(tm.group(3), tm.group(4))); continue
        if header and times is not None:
            buf.append(line)
    flush()
    return ep


def load_show(folder: str | Path) -> list[Episode]:
    return sorted((parse_episode(f) for f in Path(folder).glob("*.txt")), key=lambda e: e.num)
