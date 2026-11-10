"""Writes a small, original 3-episode demo show in the same screenplay format as the input pack.

It exists so the hosted demo has something to run on without using Kuku's confidential scripts.
    python samples/make_demo_show.py   ->  samples/demo_show/*.txt
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parent / "demo_show"

# (kind, header, seconds, text). kind: C=camera, A=action, S=sound FX, L=line (header = "NAME (Tone)")
EPISODES = [
    {
        "title": "The Auction",
        "logline": "Mara Quinn, the disinherited daughter of a shipping family, is forced to watch her late mother's "
                   "necklace auctioned off by her stepsister, until a silent stranger in the back row places a bid "
                   "nobody can match.",
        "continuity": "First episode. Establishes Mara's disinheritance, her stepsister Celeste and the stranger, Adrian.",
        "scenes": [("INT. QUINN ESTATE BALLROOM - NIGHT", [
            ("C", "", 3.0, "Wide shot of a glittering ballroom; guests in evening wear face a small auction stage."),
            ("A", "", 3.0, "Celeste lifts a sapphire necklace from a velvet case and holds it up to the crowd."),
            ("L", "CELESTE (Gloating, Cruel)", 2.6, "Lot nine. My stepsister's dead mother's sapphires."),
            ("C", "", 2.0, "Close-up on Mara at the edge of the room, frozen, a serving tray in her hands."),
            ("L", "MARA (Shocked, Whispering)", 2.0, "You promised me that necklace."),
            ("L", "CELESTE (Mocking)", 3.0, "I promised you a job, Mara. Keep pouring the champagne."),
            ("A", "", 3.2, "Guests laugh. Mara's tray tilts and a glass shatters on the marble floor."),
            ("S", "", 1.5, "Sharp crash of breaking glass, then silence."),
            ("L", "MOTHER-IN-LAW (Cold, Commanding)", 3.0, "Clean it up. On your knees, where you belong."),
            ("C", "", 2.5, "Low angle as Mara kneels among the shards, her hand bleeding."),
            ("L", "CELESTE (Smug)", 2.4, "Bidding starts at fifty thousand. Anyone?"),
            ("L", "GUEST (Amused)", 1.6, "Fifty-five!"),
            ("L", "GUEST 2 (Eager)", 1.6, "Sixty!"),
            ("A", "", 3.0, "In the last row, a man in a plain grey coat raises a single finger without standing."),
            ("L", "ADRIAN (Calm, Lethal)", 2.4, "Two million."),
            ("S", "", 2.0, "The room falls silent; a gasp ripples through the guests."),
            ("C", "", 2.6, "Close-up on Celeste, her smile collapsing."),
            ("L", "CELESTE (Stunned)", 2.0, "Who are you?"),
            ("A", "", 3.2, "Adrian walks to Mara, kneels in the glass beside her and wraps her bleeding hand in his handkerchief."),
            ("L", "ADRIAN (Quiet, Protective)", 3.0, "The necklace is hers. So is everything you took from her."),
            ("L", "MARA (Trembling)", 2.0, "I don't even know your name."),
            ("L", "ADRIAN (Ominous)", 3.0, "You will. By morning, so will your whole family."),
            ("S", "", 2.6, "Low ominous string swell into a cliffhanger sting."),
            ("C", "", 1.0, "Cut to black."),
        ])],
    },
    {
        "title": "The Contract",
        "logline": "Celeste frames Mara for stealing the sapphires, and the police arrive at dawn; Adrian offers Mara "
                   "a way out, but only if she signs a marriage contract with a man she met last night.",
        "continuity": "Continues from the auction. Adrian's identity is still unknown.",
        "scenes": [("INT. SERVANTS' QUARTERS - DAWN", [
            ("S", "", 2.0, "Fists pounding on a wooden door."),
            ("L", "OFFICER (Barking)", 2.4, "Mara Quinn! Open the door, police!"),
            ("C", "", 2.4, "Mara jolts awake in a narrow bed, the sapphire necklace on the nightstand beside her."),
            ("A", "", 3.0, "The door bursts open. Two officers and Celeste step inside."),
            ("L", "CELESTE (Venomous, Triumphant)", 3.0, "There. I told you the thief would keep it close."),
            ("L", "MARA (Desperate)", 2.6, "He bought it for me! You were all there!"),
            ("L", "OFFICER (Cold)", 2.6, "The buyer never paid. Hands behind your back."),
            ("A", "", 3.0, "An officer snaps handcuffs onto Mara's wrists and drags her into the corridor."),
            ("L", "CELESTE (Whispering, Cruel)", 3.2, "Prison suits you, sister. Nobody visits a thief."),
        ]), ("EXT. QUINN ESTATE DRIVEWAY - DAWN", [
            ("C", "", 2.6, "A black car blocks the police van. Adrian steps out holding a leather folder."),
            ("L", "ADRIAN (Calm, Commanding)", 2.6, "Release her. The money cleared ten minutes ago."),
            ("L", "OFFICER (Uncertain)", 2.0, "Sir, the family filed a complaint."),
            ("L", "ADRIAN (Icy)", 3.0, "Then the family can explain the forged complaint to my lawyers."),
            ("A", "", 3.0, "Adrian opens the folder and holds out a pen to Mara, still in handcuffs."),
            ("L", "ADRIAN (Low, Serious)", 3.2, "Sign this and no one in this house can touch you again."),
            ("L", "MARA (Wary)", 2.0, "What is it?"),
            ("L", "ADRIAN (Matter-of-fact)", 2.4, "A marriage contract. One year."),
            ("C", "", 2.4, "Close-up on Celeste in the doorway, her face draining of colour."),
            ("L", "MARA (Defiant)", 3.0, "Why would a stranger marry a disgraced maid?"),
            ("L", "ADRIAN (Ominous)", 3.0, "Because your stepmother poisoned my father. And you are my only witness."),
            ("S", "", 2.5, "Thunder cracks; ominous drone swells to a cliffhanger sting."),
            ("C", "", 1.0, "Cut to black."),
        ])],
    },
    {
        "title": "The Wedding Toast",
        "logline": "At the rushed wedding, Celeste raises a toast to expose Mara as a gold-digger, but Adrian answers "
                   "with a toast of his own that reveals who he really is and why he came back.",
        "continuity": "One week later. Mara and Adrian marry under the contract.",
        "scenes": [("INT. HARBOUR HOTEL TERRACE - NIGHT", [
            ("C", "", 2.6, "Wide shot of a small wedding party on a terrace over the harbour, lanterns swaying."),
            ("A", "", 3.0, "Celeste stands and taps a knife against her glass, smiling at the guests."),
            ("L", "CELESTE (Sweet, Venomous)", 3.0, "A toast to the bride, who went from maid to millionaire in a week."),
            ("A", "", 2.6, "Guests snicker. Mara grips the edge of the table."),
            ("L", "CELESTE (Mocking)", 3.4, "How much did he pay for you, Mara? More than the necklace?"),
            ("S", "", 1.6, "A wine glass slams down on the table."),
            ("L", "MARA (Furious, Shaking)", 2.6, "Sit down, Celeste."),
            ("L", "STEPMOTHER (Cold, Superior)", 3.0, "Let her speak. Someone should warn this poor man."),
            ("C", "", 2.4, "Close-up on Adrian, utterly calm, turning his glass slowly."),
            ("A", "", 3.0, "Adrian rises. The terrace goes quiet."),
            ("L", "ADRIAN (Calm, Lethal)", 3.4, "My turn. To my father, Thomas Vance, who drank a toast in this hotel."),
            ("L", "ADRIAN (Cold)", 3.0, "And died before morning. Arsenic, the coroner said."),
            ("C", "", 2.2, "Close-up on the Stepmother, her glass trembling."),
            ("L", "STEPMOTHER (Panicked)", 2.0, "Vance? The Vance shipping line?"),
            ("L", "ADRIAN (Triumphant, Icy)", 3.2, "The line you've been trying to buy for ten years. I own it now."),
            ("A", "", 3.0, "Two detectives step out of the lantern light behind the Stepmother's chair."),
            ("L", "ADRIAN (Ominous)", 2.8, "And tonight, someone at this table is leaving in handcuffs."),
            ("L", "CELESTE (Horrified)", 2.0, "Mother... what did you do?"),
            ("S", "", 2.6, "Heartbeat sound, then a sharp cliffhanger sting."),
            ("C", "", 1.0, "Cut to black."),
        ])],
    },
]

HEAD = {"C": "CAMERA", "A": "ACTION", "S": "SOUND FX"}


def mmss(t: float) -> str:
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:05.2f}"


def write_episode(n: int, ep: dict) -> Path:
    t = 0.0
    out = [f"EPISODE NUMBER: Episode {n}", f"EPISODE LOGLINE: {ep['logline']}", f"CONTINUITY NOTES: {ep['continuity']}",
           "", "--- SCRIPT START ---", ""]
    for si, (heading, beats) in enumerate(ep["scenes"], 1):
        total = sum(b[2] for b in beats)
        out += [f"SCENE {si:02d}", f"Scene heading: {heading}", f"Scene start: {mmss(t)}", f"Scene end: {mmss(t + total)}",
                "", "Actions and dialogue:", ""]
        for kind, header, dur, text in beats:
            h = header if kind == "L" else HEAD[kind]
            body = f'"{text}"' if kind == "L" else text
            out += [f"**{h}:**", f"Start: ({mmss(t)}) | End: ({mmss(t + dur)})", body, ""]
            t = round(t + dur, 2)
    out += ["--- SCRIPT END ---", ""]
    path = OUT / f"episode-{n:03d}-{ep['title'].replace(' ', '-')}.txt"
    path.write_text("\n".join(out), encoding="utf-8")
    return path


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for i, ep in enumerate(EPISODES, 1):
        print(write_episode(i, ep))
