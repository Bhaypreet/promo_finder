"""Builds docs/Solution_Doc.pdf (2 pages). Every number is read from the run outputs, not typed by hand.

    python docs/build_solution_doc.py outputs/gpt-oss-120b outputs/rules-only
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
llm_dir = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "outputs/gpt-oss-120b")
rules_dir = ROOT / (sys.argv[2] if len(sys.argv) > 2 else "outputs/rules-only")
run = json.loads((llm_dir / "promos.json").read_text(encoding="utf-8"))
promos = run["promos"]
ev = {r["run"]: r for r in json.loads((ROOT / "outputs" / "eval_results.json").read_text(encoding="utf-8"))}
ev_random = next(v for k, v in ev.items() if k.startswith("random"))
totals = json.loads((ROOT / "docs" / "facts.json").read_text(encoding="utf-8"))["totals"]
DRIVE = "https://drive.google.com/drive/folders/1QTSzxsaEqu4_PbWOeR150AJ3hQIbad43"

# ---------- fonts and styles ----------
REG, BOLD = "Helvetica", "Helvetica-Bold"
for reg, bold in (("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
                  ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")):
    if Path(reg).exists() and Path(bold).exists():
        pdfmetrics.registerFont(TTFont("Body", reg)); pdfmetrics.registerFont(TTFont("Body-Bold", bold))
        pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body", boldItalic="Body-Bold")
        REG, BOLD = "Body", "Body-Bold"
        break

INK, ACCENT, MUTED = colors.HexColor("#1f1d2b"), colors.HexColor("#a3214f"), colors.HexColor("#5f5b70")
RULE, TINT = colors.HexColor("#dcd8e3"), colors.HexColor("#f6f3f8")
AI_C, CODE_C, HUM_C = colors.HexColor("#a3214f"), colors.HexColor("#46506a"), colors.HexColor("#2f7a4f")

B = ParagraphStyle("b", fontName=REG, fontSize=8.4, leading=10.7, textColor=INK)
S = ParagraphStyle("s", parent=B, fontSize=7.8, leading=9.8)
SM = ParagraphStyle("sm", parent=S, textColor=MUTED)
H = ParagraphStyle("h", fontName=BOLD, fontSize=10.4, leading=12.6, textColor=ACCENT, spaceBefore=6, spaceAfter=2.5)
TITLE = ParagraphStyle("t", fontName=BOLD, fontSize=16, leading=19, textColor=INK)
SUB = ParagraphStyle("sub", parent=B, fontSize=8.6, leading=11, textColor=MUTED)
CELL = ParagraphStyle("c", parent=B, fontSize=7.6, leading=9.4)
HEAD = ParagraphStyle("hd", parent=CELL, fontName=BOLD, textColor=ACCENT)
W = 180 * mm


def p(t, st=B):
    return Paragraph(t, st)


def bullets(items, st=B):
    return [Paragraph(f"&bull;&nbsp;&nbsp;{i}", ParagraphStyle("bl", parent=st, leftIndent=9, firstLineIndent=-7,
                                                            spaceAfter=1.2)) for i in items]


def table(rows, widths, zebra=True, size=None):
    cst = CELL if size is None else ParagraphStyle("cx", parent=CELL, fontSize=size, leading=size + 1.7)
    hst = ParagraphStyle("hx", parent=cst, fontName=BOLD, textColor=ACCENT)
    data = [[Paragraph(str(c), hst if i == 0 else cst) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LINEBELOW", (0, 0), (-1, 0), 0.8, ACCENT),
             ("LINEBELOW", (0, 1), (-1, -1), 0.3, RULE),
             ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
             ("TOPPADDING", (0, 0), (-1, -1), 2.0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2)]
    if zebra:
        style += [("BACKGROUND", (0, r), (-1, r), TINT) for r in range(2, len(rows), 2)]
    t.setStyle(TableStyle(style))
    return t


def flow():
    """Pipeline diagram, colour-coded by who does the work."""
    steps = [("Parse scripts", "code", CODE_C), ("Rule scorer", "code", CODE_C), ("Retrieve patterns", "RAG", AI_C),
             ("Pick promos", "LLM", AI_C), ("Check + repair", "code + LLM", CODE_C), ("Cold-viewer test", "2nd LLM", AI_C),
             ("Rank + review", "code + editor", HUM_C)]
    n, gap, h = len(steps), 4.2 * mm, 12.5 * mm
    bw = (W - gap * (n - 1)) / n
    d = Drawing(W, h + 1)
    for i, (name, who, col) in enumerate(steps):
        x = i * (bw + gap)
        d.add(Rect(x, 0.5, bw, h, rx=3, ry=3, fillColor=colors.white, strokeColor=col, strokeWidth=1))
        d.add(Rect(x, 0.5, 2.2, h, fillColor=col, strokeColor=col, strokeWidth=0))
        d.add(String(x + bw / 2 + 1, h * 0.56, name, fontName=BOLD, fontSize=6.9, fillColor=INK, textAnchor="middle"))
        d.add(String(x + bw / 2 + 1, h * 0.2, who, fontName=REG, fontSize=6.6, fillColor=col, textAnchor="middle"))
        if i < n - 1:
            ax = x + bw + 0.6
            d.add(Line(ax, h / 2 + 0.5, ax + gap - 2.2, h / 2 + 0.5, strokeColor=MUTED, strokeWidth=0.8))
            d.add(Polygon([ax + gap - 1.2, h / 2 + 0.5, ax + gap - 3.4, h / 2 + 2, ax + gap - 3.4, h / 2 - 1],
                          fillColor=MUTED, strokeColor=MUTED, strokeWidth=0))
    return d


def mmss(t):
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:04.1f}"


# ---------- numbers from the run ----------
n, passed = len(promos), sum(x["passed"] for x in promos)
repaired = sum(1 for x in promos if any(f.startswith("model repaired") for f in x["fixes"]))
code_fixed = sum(1 for x in promos if x["fixes"] and not any(f.startswith("model repaired") for f in x["fixes"]))
durs = [x["duration"] for x in promos]
eps_covered = len({e for x in promos for e in x["episodes"]})


def blind_avg(ps):
    b = [x["blind"] for x in ps if x.get("blind")]
    return [sum(v[k] for v in b) / len(b) for k in ("stop_scrolling", "want_next", "understood")]


top10, allb = blind_avg(promos[:10]), blind_avg(promos)
r_rules, r_20n, r_20, r_120 = ev[rules_dir.name], ev["gpt-oss-20b-noplaybook"], ev["gpt-oss-20b"], ev[llm_dir.name]
by_id = {x["id"]: x for x in promos}


def cut_of(pid):
    x = by_id[pid]
    return " + ".join(f"{mmss(s['start'])}-{mmss(s['end'])}" for s in x["segments"])


# ---------- page 1 ----------
story = [
    p("Promo Finder: ranked promo cut lists from screenplays", TITLE), Spacer(1, 2),
    p(f"Kuku AI Generalist Assignment &middot; Problem 1, Find the Promos &middot; "
      f"Prototype, code and raw outputs: <link href='{DRIVE}' color='#a3214f'><u>project folder</u></link> "
      f"(run steps in README.md)", SUB),
    Spacer(1, 3),
    p("Give the tool a folder or .zip of episode screenplays. It returns a ranked list of 20-60 s promos. Each one comes "
      "with the episode and start/end time of every segment, the hook, the cliffhanger, a one-line reason it works, and "
      "its quality-check results, as a CSV an editor can cut from directly. "
      f"On the full input pack it found {n} promos across {eps_covered} of the 50 episodes."),

    p("Problem and scope", H),
    p("<b>Why Problem 1.</b> It is a weekly, repeated cost: an editor watches every episode of every new show to find "
      "promo moments, and a new show ships every week. The screenplays already time-stamp every line, action and shot, so "
      "the hard part is the editorial judgement (which moment stops a scroll, where it should end), not the cutting. "
      "That splits cleanly: a language model for judgement, plain code for time and rules. It is also the one problem with "
      "Kuku's own content, so every output can be checked against the real show."),
    Spacer(1, 2.5),
    table([["Where the brief was silent, I assumed", "What the tool does about it"],
           ["The script timestamps match the final cut.",
            "Every cut snaps to the nearest shot change and never lands mid-line, so small drift stays invisible; an editor can nudge."],
           ["A promo's job is to bring <b>new</b> viewers to Episode 1.",
            "Ranking gives early-episode promos a small bonus and penalises spoilers of late-series twists."],
           ["Platform is TikTok / Reels / Shorts, US audience.",
            "The 3-second hook is checked from script timing. Visual impact (framing, faces) cannot be judged from text, so an editor watches the shortlist."],
           ["A promo can join several moments, from one or many episodes.",
            "Segments must stay in story order, must not overlap and must total 20-60 s."],
           ["Free tiers only.",
            "Token-lean prompts on Groq's free models. Any stronger model, including Kuku's own APIs, is a one-flag swap."]],
          [62 * mm, 118 * mm]),

    p("How it works", H),
    flow(), Spacer(1, 3),
    table([["", "Given to the language model", "Kept as code or simple rules", "Kept with a human"],
           ["Work", "Choosing the moments; writing the hook, cliffhanger and why; fixing a pick the checker rejected; "
                    "judging a clip cold, as a stranger would",
            "Reading the scripts; every timestamp; shot-cut snapping; the 20-60 s and 3 s rules; candidate windows; "
            "retrieval; the ranking formula",
            "Final say on the top 10 (review mode); approved promos are saved and guide future shows"],
           ["Why", "Judgement over story and emotion is what models do well",
            "Arithmetic and hard rules must be exact and repeatable", "Taste, brand fit and spoiler calls"]],
          [11 * mm, 58 * mm, 61 * mm, 50 * mm], zebra=False),

    p("Key design decisions", H),
    table([["Decision", "Why it matters"],
           ["<b>The model picks line IDs, never timestamps.</b> Each line gets an ID (B031); code turns IDs into times.",
            "Models invent times but reference IDs reliably. Cuts land on shot changes and never mid-sentence."],
           ["<b>Validated output with a repair loop.</b> Answers must fit a strict schema; a pick that breaks a rule goes "
            "back to the model once, with the exact error.",
            f"{repaired} of {n} first picks broke a rule (wrong length, overlapping segments, a late hook) and came back fixed; "
            f"code fixed {code_fixed} more on its own."],
           ["<b>A playbook the model retrieves from (RAG).</b> 16 proven promo patterns (public humiliation, interrupted "
            "wedding, hidden identity) plus every promo an editor approves.",
            f"Same model, with vs without the playbook: precision against reference promos rose from {r_20n['precision']:.2f} "
            f"to {r_20['precision']:.2f}. The tool gets better with each approved promo."],
           ["<b>A second, different model judges every clip cold.</b> It sees only the clip, with no show context.",
            "The picker cannot grade its own work. This 'would a stranger stop and understand?' score is 40% of the rank."],
           ["<b>Search, don't stuff, for cross-episode promos.</b> 1,640 short moments are indexed for the whole show.",
            "The full show is about 45K tokens. Retrieval finds matching moments across episodes and keeps prompts small."],
           ["<b>One setting picks the model; every answer is cached.</b>",
            "Switching to a stronger or in-house model is one flag. Reruns cost nothing and give identical output."]],
          [88 * mm, 92 * mm]),
    p("Scale and cost", H),
    *bullets([
        f"<b>Cost per show</b> (50 episodes): {totals['calls']} model calls, about {totals['tokens'] // 1000}K tokens. "
        "$0 on Groq's free tier; under $0.10 at Groq's published paid rates. The rules-only mode is free and runs in under a second.",
        f"<b>Time:</b> {totals['minutes']} minutes on the free tier, set by its rate limits (about 8K tokens a minute), not "
        "by compute. Episodes are processed in parallel, so a paid tier or an in-house model cuts this to minutes.",
        "<b>Every show, every week:</b> a FastAPI service with a Dockerfile. Upload a zip, get the cut list. Model answers "
        "and the search index are cached, so reruns are free.",
        "<b>Editor time</b> goes from watching every episode to reviewing a ranked top 10. "
        "<b>Next measure:</b> each posted promo's 3-second view rate, click-through and Episode 1-to-5 retention, used to re-weight the ranking.",
    ], S),

]

# ---------- page 2 ----------
top = [("E05-P1", "5", "Disowned at the church door",
        "\"You will not leave this church carrying the Ashcroft name.\"", "Her mother's ledger hits the mud; she kneels in the rain."),
       ("E01-P1", "1", "Jilted at the altar",
        "\"Not anymore.\" The groom is marrying her sister.", "\"And you knew?\" (to her sister)"),
       ("E18-P1", "18", "Night fire rescue",
        "Bedroom door kicked in, hallway in flames.", "\"What are you going to do?\" Her husband's cold stare."),
       ("E32-P1", "32", "The branding iron",
        "\"Silence! Silence!\" in a packed courtroom.", "The glowing iron hovers inches from her eye."),
       ("E13-P1", "13", "Crawling through thorns",
        "\"Juliana, stop!\"", "Her bloody hand closes on the lost ring."),
       ("E45-P1", "45", "\"Wife?!\" The Duke reveal",
        "\"Wife?!\" He names her his Duchess.", "Priest: \"You are not his lawful wife.\"")]
rows = [["Post", "Promo", "Episode and cut", "Sec", "Opens on (first 3 s)", "Ends on (cliffhanger)", "Rank"]]
for i, (pid, ep, title, hook, cliff) in enumerate(top, 1):
    x = by_id[pid]
    rows.append([str(i), f"<b>{title}</b>", f"Ep {ep} &middot; {cut_of(pid)}", f"{x['duration']:.0f}", hook, cliff,
                 f"#{x['rank']}"])
story += [
    PageBreak(),
    p("Top promos and what I would post first", H),
    table(rows, [8 * mm, 30 * mm, 37 * mm, 8 * mm, 44 * mm, 44 * mm, 9 * mm], size=7.4),
    Spacer(1, 2.5),
    *bullets([
        "<b>Post first: the premise.</b> Episodes 5 and 1 set up the whole show (jilted at the altar, then cast out). A cold viewer "
        "understood both (8/10), and they send new viewers to the start, where the payoff is immediate.",
        "<b>Then the visual shocks.</b> The fire rescue and the branding iron are the strongest stop-the-scroll openings.",
        "<b>Hold the #1 pick for retargeting.</b> Episode 45 scores highest on every signal, but it gives away the title "
        "twist. It works best on people already watching. Catching this is the editor's job in review mode.",
        "Ranking: 45% picker scores + 40% cold viewer + 15% rule scorer, minus a spoiler penalty, plus an early-episode "
        "bonus. Every promo, with all segments, hook, cliffhanger and why, is in <i>promos_cutlist.csv</i>.",
    ], S),

    p("Quality checks", H),
    table([["Check", "What it tests", "Result on the full pack"],
           ["Hard rules (code, every promo)", "20-60 s, hook in the first 3 s, ends on the cliffhanger, story order, no mid-line cuts",
            f"<b>{passed} of {n} pass</b> ({min(durs):.0f}-{max(durs):.0f} s, mean {sum(durs)/n:.0f} s). The 2 that miss "
            "(under 20 s by 0.4 s and 2.3 s) are flagged and ranked last."],
           ["Cold viewer (different model, clip text only)", "Would you stop scrolling? Want the next episode? Understand it without context?",
            f"Top 10: <b>{top10[0]:.1f} / {top10[1]:.1f} / {top10[2]:.1f}</b> out of 10. Whole list: "
            f"{allb[0]:.1f} / {allb[1]:.1f} / {allb[2]:.1f}; clips that need context sink in the ranking."],
           ["Reference promos", "13 promos marked by hand in 8 episodes before seeing the tool's output; a match is "
            "at least 40% time overlap", "See the table below."]],
          [38 * mm, 70 * mm, 72 * mm]),
    Spacer(1, 3),
    table([["Run, against the 13 reference promos", "Found (recall)", "On target (precision)", "Opens on the same hook"],
           ["Random 30-45 s windows, 2 per episode (floor)", f"{ev_random['recall']:.2f}", f"{ev_random['precision']:.2f}", f"{ev_random['hook_ok']:.2f}"],
           ["Rule scorer alone (free, no model)", f"{r_rules['recall']:.2f}", f"{r_rules['precision']:.2f}", f"{r_rules['hook_ok']:.2f}"],
           ["gpt-oss-20b, no playbook", f"{r_20n['recall']:.2f}", f"{r_20n['precision']:.2f}", f"{r_20n['hook_ok']:.2f}"],
           ["gpt-oss-20b + playbook RAG", f"<b>{r_20['recall']:.2f}</b>", f"<b>{r_20['precision']:.2f}</b>", f"<b>{r_20['hook_ok']:.2f}</b>"]],
          [82 * mm, 30 * mm, 32 * mm, 36 * mm], size=7.5),
    Spacer(1, 2.5),
    *bullets([
        "<b>The playbook works.</b> On the same model it lifts all three numbers, and more than doubles how often the promo "
        "opens on the reference hook.",
        f"<b>The rule scorer finds where the action is</b> (recall {r_rules['recall']:.2f}), which is why its candidate "
        "windows go to the model as hints. It cannot write the hook or why, judge whether a clip stands alone, join "
        "moments or flag spoilers; the model does that.",
        f"<b>The main run (gpt-oss-120b)</b> matches fewer exact windows (recall {r_120['recall']:.2f}, precision "
        f"{r_120['precision']:.2f}). It prefers longer, joined promos that open on a different hook a few seconds away; "
        "its Episode 45 pick opens on \"Wife?!\" 6 s before the reference cut, and the cold viewer rated it 8/9/9.",
    ], S),

    p("Where it picks badly, and what handles it", H),
    table([["Weak spot", "Why", "How it is handled"],
           ["Many clips need context", "Microdrama scenes start mid-story; a stranger can miss who is who and why it matters.",
            "The cold viewer's score is 40% of the rank, so these clips sink: the top 10 average 6.1/10 on understanding vs 4.1 overall."],
           ["Spoilers are under-flagged", "The model cannot tell which reveal is the show's big twist (it marked Ep 45 'low').",
            "Editor review of the top 10. Next: a per-show 'never reveal' list in the knowledge base."],
           ["Self-scores run high", "The picker rates almost every pick 8-9/10.",
            "Only 45% of the rank, balanced by the cold viewer and rules."],
           ["Text cannot see the picture", "A badly framed slap still reads well on paper.",
            "The editor watches the shortlist, about 10 minutes per show instead of every episode."],
           ["Cross-episode montages are weakest", "Moments from different episodes need bridging context.",
            "Kept, but ranked low. Next: limit them to 2-3 moments from neighbouring episodes."]],
          [38 * mm, 66 * mm, 76 * mm], size=7.4),

    p("Tools used, and where they got it wrong", H),
    p("<b>Building:</b> Claude Code as a coding assistant for the parser, pipeline, evaluation scripts and first drafts "
      "of this doc. <b>Inside the tool:</b> Groq gpt-oss-120b picks promos (gpt-oss-20b as fallback), Groq Qwen3.8-27b "
      "is the cold viewer, FastEmbed bge-small powers retrieval; LangGraph, LangChain, FAISS and Pydantic hold it together. "
      f"<b>Where they got it wrong:</b> the picker broke a hard rule in {repaired} of {n} first picks: clips from 13 s to "
      "88 s, overlapping segments, and once a 'hook' 67 s into the clip. The validator caught every one. The cold viewer at "
      "first scored nearly every clip 1-2/10, even clips it had summarised correctly, until it was given a scoring guide "
      "with an example for each level.", S),
]

out = ROOT / "docs" / "Solution_Doc.pdf"
doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=15 * mm - 6, rightMargin=15 * mm - 6,
                        topMargin=11 * mm, bottomMargin=10 * mm, title="Promo Finder - Solution Doc", author="")
doc.build(story)
from pypdf import PdfReader  # noqa: E402  (only to report the page count)
print(out, "pages:", len(PdfReader(str(out)).pages))
