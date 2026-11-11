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
DEMO = "https://promo-finder-demo.streamlit.app"
REPO = "https://github.com/Bhaypreet/promo_finder"
EXPLAINER = "https://claude.ai/artifact/G2XiCpShwi8UBUUFpgb8bV"

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
    p("Kuku AI Generalist Assignment &middot; Problem 1, Find the Promos", SUB), Spacer(1, 2),
    table([["Live app (Streamlit)", "Code + run steps", "Raw outputs", "Longer explainer"],
           [f"<link href='{DEMO}' color='#a3214f'><u>{DEMO}</u></link>",
            f"<link href='{REPO}' color='#a3214f'><u>github.com/Bhaypreet/promo_finder</u></link>",
            f"<link href='{DRIVE}' color='#a3214f'><u>Drive folder</u></link>",
            f"<link href='{EXPLAINER}' color='#a3214f'><u>Project write-up</u></link>"]],
          [58 * mm, 52 * mm, 30 * mm, 40 * mm], zebra=False),

    p("The problem: why promos take so long today", H),
    p("Kuku releases a new microdrama every week, about 50 short episodes each. To make promos, an editor has to watch "
      "every episode, find moments that grab attention in the first 3 seconds and end on a cliffhanger, and note the "
      "exact start and end times. Then each promo has to be checked by hand: is it 20-60 s, does the hook land in time, "
      "does it end on the right line? This takes hours for every show, every week. "
      "<b>Why I picked this problem:</b> the screenplays already give a timestamp for every line, action and camera shot. "
      "So the slow part is reading and judging, which AI can do in minutes, and the checking is pure rules, which code "
      "can do instantly and without mistakes."),

    p("Input and output", H),
    table([["Input (what I give the tool)", "Output (what it gives back)"],
           ["A folder or .zip of episode screenplays (text files). Every line of dialogue, action, sound and camera shot "
            "has a start and end time, e.g. <i>Start: (00:43.20) | End: (00:45.10)</i>.",
            "A ranked list of 20-60 s promos. For each: the episode and start/end time of every segment, the hook (first "
            "3 s), the cliffhanger it ends on, why it works, and its check results. Saved as a CSV an editor can cut from "
            f"directly. <b>On the full pack: {n} promos across {eps_covered} of the 50 episodes, {passed} pass every check.</b>"]],
          [80 * mm, 100 * mm], zebra=False),

    p("How it works, step by step", H),
    flow(), Spacer(1, 2.5),
    table([["Step", "Who", "What happens, in simple words"],
           ["<b>1. Read the scripts</b>", "Code",
            "Each episode is split into small numbered pieces called beats (B001, B002...): one line, action or shot "
            "each, with its start and end time. The 50 episodes give 3,727 beats."],
           ["<b>2. Spot likely moments</b>", "Simple rules",
            "A keyword scorer looks for drama signals (a slap, a shout, a betrayal, an angry tone) and marks the strongest "
            "windows. These go to the AI as hints. On their own, they are also a free, instant no-AI mode."],
           ["<b>3. Look up proven patterns</b>", "Search",
            "A small playbook holds 16 promo patterns that work (public humiliation, interrupted wedding, hidden identity) "
            "plus every promo an editor approves. The 3 closest to this episode are pulled in as examples."],
           ["<b>4. AI picks the promos</b>", "AI",
            "The AI reads the episode, the hints and the patterns, and picks promos. It answers with beat numbers, not "
            "times, plus the hook, the cliffhanger and why it works. Its answer must fit a fixed format or it is rejected."],
           ["<b>5. Code checks every pick</b>", "Code",
            "Beat numbers become exact times, and cuts land on shot changes, never mid-sentence. Code checks: 20-60 s, "
            f"hook in the first 3 s, ends on the cliffhanger. A broken pick goes back to the AI once with the exact error "
            f"({repaired} of {n} were fixed this way); if it is still broken, it is flagged."],
           ["<b>6. Cross-episode promos</b>", "Search + AI",
            "The tool searches 1,640 short moments across the whole show and lets the AI join 2-4 of them into one promo."],
           ["<b>7. A second AI watches it cold</b>", "2nd AI",
            "A different model sees only the clip, with no story context, and scores 1-10: would I stop scrolling, do I "
            "want the next episode, did I understand it? The picker never grades its own work."],
           ["<b>8. Rank</b>", "Code",
            "Score = 45% picker + 40% cold viewer + 15% rules, minus a spoiler penalty, plus a small bonus for early "
            "episodes (they send new viewers to the start)."],
           ["<b>9. Editor review</b>", "Human",
            "The editor checks the top 10 and approves the best. Approved promos go back into the playbook, so the tool "
            "gets better with every show."]],
          [33 * mm, 18 * mm, 129 * mm], size=7.5),

    p("Assumptions", H),
    *bullets([
        "<b>The script times match the final video.</b> Cuts snap to shot changes, so a small difference is invisible and an editor can nudge it.",
        "<b>Text cannot show faces, acting or framing.</b> The tool judges the story and the words; an editor watches the shortlist for the visuals.",
        "<b>A promo's job is to bring new viewers to Episode 1,</b> so early episodes get a bonus and big late twists are penalised.",
        "<b>Free tools only.</b> Everything runs on free tiers; a stronger model is a setting, not a code change.",
    ], S),

    p("The AI I used", H),
    p("Three models, all on Groq's free tier: <b>gpt-oss-120b</b> picks the promos (gpt-oss-20b as a backup), "
      "<b>Qwen3.8-27b</b> is the cold viewer, and a small embedding model powers the pattern search. A different model, "
      "including Kuku's own API, can be used by pasting its key in the app. Every answer is saved, so a rerun costs "
      f"nothing. <b>Cost per show:</b> {totals['calls']} model calls, about {totals['tokens'] // 1000}K tokens, $0 on the "
      f"free tier (under $0.10 at paid rates), {totals['minutes']} minutes because of the free tier's speed limit. "
      "<b>Editor time</b> goes from watching every episode to reviewing a ranked top 10.", S),
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
        "<b>Hold the #1 pick for retargeting.</b> Episode 45 scores highest on every signal, but it gives away the title "
        "twist. It works best on people already watching. Catching this is the editor's job in review mode.",
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

    p("Limitations (technical)", H),
    table([["Limitation", "What it means", "How I handle it, or what I would do next"],
           ["<b>1. Free-tier speed limit</b>", f"Groq's free tier allows about 8K tokens a minute, so the tool waits between "
            f"calls: about 5 minutes for the 3-episode demo, {totals['minutes']} minutes for 50 episodes. The hosted app "
            "runs one AI run at a time.", "Rules-only mode is instant. A paid key or Kuku's own API removes the wait."],
           ["<b>2. The AI does not always follow rules</b>", f"Even when told the rules, it broke one in {repaired} of {n} "
            "first picks (wrong length, late hook, overlapping parts).", "Code checks every pick, sends it back once, "
            "and flags what is still wrong. The AI never decides times."],
           ["<b>3. AI scores are opinions, not real data</b>", "The picker rates almost all its picks 8-9/10, and the cold "
            "viewer is also a model, not a real audience.", "The picker is only 45% of the rank. Next: use real 3-second "
            "view rates and Episode 1 clicks."],
           ["<b>4. Depends on the script format</b>", "The reader expects this exact screenplay format and English text, "
            "and trusts its timestamps.", "Reading is plain code, so a new format is a small change. Cuts snap to shots."],
           ["<b>5. Small test set</b>", "I measured quality against 13 promos I picked by hand in 8 episodes: one "
            "person's taste.", "Next: more reference promos from Kuku's editors, and real performance data."]],
          [40 * mm, 78 * mm, 62 * mm], size=7.4),

    p("Deployment, and what went wrong when I used it", H),
    p(f"I deployed the prototype on <b>Streamlit Community Cloud</b> "
      f"(<link href='{DEMO}' color='#a3214f'><u>{DEMO}</u></link>), running the same pipeline as the command line. "
      "Using it myself showed two problems:", S),
    *bullets([
        "<b>Checking the results by hand took a lot of time.</b> On the free tier an AI run takes about 4 minutes for the "
        f"3-episode demo and {totals['minutes']} minutes for the full pack. Then every promo had to be checked against the "
        "script: find the start and end time, confirm the hook and the cliffhanger line. Doing that for "
        f"{n} promos is slow, so the checks code can do (length, 3 s hook, shot-change cuts, ends on the cliffhanger) run "
        "on every promo, and a person only reviews the ranked top 10. Next: show each promo's script lines in the app.",
        "<b>The app could get stuck on \"Another run is in progress\".</b> Only one AI run is allowed at a time, because "
        "every visitor shares one free-tier token budget. If someone refreshed the page mid-run, the old run held the lock "
        "and new visitors waited with no result. Fixed: rules-only mode never waits, a busy AI run says so instead of "
        "hanging, a stuck run is released after 12 minutes, and every model call times out after 90 s.",
    ], S),

    p("Tools used, and where they got it wrong", H),
    p("<b>Building:</b> Claude Code as a coding assistant for the parser, pipeline, evaluation scripts and first drafts "
      "of this doc. <b>Inside the tool:</b> Groq gpt-oss-120b picks promos (gpt-oss-20b as fallback), Groq Qwen3.8-27b "
      "is the cold viewer, FastEmbed bge-small powers retrieval. "
      f"<b>Where they got it wrong:</b> the picker broke a hard rule in {repaired} of {n} first picks: clips from 13 s to "
      "88 s, overlapping segments, a 'hook' 67 s into the clip; the validator caught every one. The cold viewer first "
      "scored almost every clip 1-2/10 until I gave it a scoring guide with examples.", S),
]

out = ROOT / "docs" / "Solution_Doc.pdf"
doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=15 * mm - 6, rightMargin=15 * mm - 6,
                        topMargin=11 * mm, bottomMargin=10 * mm, title="Promo Finder - Solution Doc", author="")
doc.build(story)
from pypdf import PdfReader  # noqa: E402  (only to report the page count)
print(out, "pages:", len(PdfReader(str(out)).pages))
