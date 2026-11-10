# Promo picks: I Married a Broken Soldier. He was a Duke

Picker: `groq:openai/gpt-oss-20b` | blind viewer: `None` | episodes: 8 | promos: 11 | pass all checks: 10 | LLM calls: 3 new + 9 from cache | runtime: 120.5 s

| # | id | segments | sec | hook | cliffhanger | score | blind stop/next/understood |
|---|---|---|---|---|---|---|---|
| 1 | E42-P1 | Ep42 00:23.40-01:17.80 | 54 | I said arrest him! | And now, Rupert... we settle what you stole. | 0.82 | - |
| 2 | E13-P1 | Ep13 00:47.00-00:56.80 + Ep13 01:14.00-01:47.00 | 43 | Juliana, stop! | Her blood‑smeared index finger brushes against a solid metallic object | 0.81 | - |
| 3 | E12-P1 | Ep12 00:13.90-01:09.50 | 56 | The proof is in his coat, Juliana. | Fail, or refuse, and your husband hangs from the gallows. | 0.79 | - |
| 4 | E24-P1 | Ep24 00:32.30-01:03.80 | 32 | The noblewoman suddenly rears back her riding crop and strikes Juliana violently across the torso. | The noblewoman threatens Juliana with a harsh command that leaves her fate uncertain. | 0.78 | - |
| 5 | E05-P3 | Ep5 01:10.30-01:31.00 | 21 | The Mysterious Bearded Man kneels beside Juliana, offering his scarred hand to retrieve the ledger. | The Mysterious Bearded Man reaches out with both hands, clasping his strong hands tenderly over hers and the book. | 0.76 | - |
| 6 | E05-P1 | Ep5 00:04.00-00:29.00 | 25 | Lord Ashcroft’s cold command: “Miss Ashcroft.” | From this moment, you are dead to the Ashcroft family. | 0.76 | - |
| 7 | E05-P2 | Ep5 00:46.60-01:09.00 | 22 | Lady Ashcroft’s venomous threat: “…that belongs to this family.” | Juliana drops to her knees onto the wet courtyard pavement, oblivious to the dirt soaking through her white bridal gown. | 0.76 | - |
| 8 | E45-P1 | Ep45 00:53.80-01:31.30 | 38 | You poisoned my mother. You tortured my wife. | No one will bow yet! | 0.72 | - |
| 9 | E41-P1 | Ep41 00:17.30-01:00.80 | 44 | Juliana is marched forward, shackled, into the cathedral | Juliana defiantly questions Catherine’s power | 0.72 | - |
| 10 | E27-P1 | Ep27 00:44.20-00:51.50 + Ep27 01:17.80-01:32.80 + Ep27 02:02.80-02:25.20 | 45 | What is your husband's name? | She secretly administers an unidentified substance to a helpless woman. | 0.71 | - |
| 11 | E45-P2 ⚠ | Ep45 00:21.80-00:24.50 + Ep45 01:11.00-01:14.50 | 6 | Alexander drops to one knee and drops the ducal cloak over Juliana | The priest’s voice booms, "You are not Duchess of Ashburton." | 0.50 | - |

## Details

### 1. E42-P1: Duke’s Reckoning (54.4s, single)
- **Segments:** Ep42 00:23.40-01:17.80
- **Hook:** I said arrest him!
- **Cliffhanger:** And now, Rupert... we settle what you stole.
- **Why:** The clip opens with a dramatic shout that stops scrolling, shows the conflict with guards, and ends on a threat that leaves viewers wanting to know the outcome.
- **Scores:** {'hook': 9.0, 'cliffhanger': 9.0, 'standalone': 9.0} | rules 0.575 | spoiler medium | pattern: other
- **Retrieved for grounding:** -

### 2. E13-P1: Thorn‑Torture & Treasure (42.8s, multi-moment)
- **Segments:** Ep13 00:47.00-00:56.80 + Ep13 01:14.00-01:47.00
- **Hook:** Juliana, stop!
- **Cliffhanger:** Her blood‑smeared index finger brushes against a solid metallic object
- **Why:** The hook grabs attention with a desperate plea, the cliffhanger teases a hidden treasure, and the two non‑overlapping segments keep the clip under 45 s while showing enough context for a new viewer.
- **Scores:** {'hook': 8.0, 'cliffhanger': 8.0, 'standalone': 9.0} | rules 0.625 | spoiler low | pattern: other
- **Retrieved for grounding:** -
- **Fixes:** model repaired it after validator feedback: too long (62.5s > 60s); segments overlap

### 3. E12-P1: The Ultimatum (55.6s, single)
- **Segments:** Ep12 00:13.90-01:09.50
- **Hook:** The proof is in his coat, Juliana.
- **Cliffhanger:** Fail, or refuse, and your husband hangs from the gallows.
- **Why:** A brutal threat and a chilling promise hook viewers, ending on a deadly ultimatum that leaves them wanting more.
- **Scores:** {'hook': 8.0, 'cliffhanger': 9.0, 'standalone': 9.0} | rules 0.5 | spoiler medium | pattern: other
- **Retrieved for grounding:** -
- **What a new viewer lacks:** Why Clarissa is threatening Alexander’s life.

### 4. E24-P1: The Strike & The Return (31.5s, single)
- **Segments:** Ep24 00:32.30-01:03.80
- **Hook:** The noblewoman suddenly rears back her riding crop and strikes Juliana violently across the torso.
- **Cliffhanger:** The noblewoman threatens Juliana with a harsh command that leaves her fate uncertain.
- **Why:** The opening strike grabs attention, and the cliffhanger leaves viewers wondering what will happen to Juliana.
- **Scores:** {'hook': 9.0, 'cliffhanger': 8.0, 'standalone': 8.0} | rules 0.425 | spoiler low | pattern: other
- **Retrieved for grounding:** -
- **Fixes:** model repaired it after validator feedback: too short (18.5s < 20s)

### 5. E05-P3: Redemption Hand (20.7s, single)
- **Segments:** Ep5 01:10.30-01:31.00
- **Hook:** The Mysterious Bearded Man kneels beside Juliana, offering his scarred hand to retrieve the ledger.
- **Cliffhanger:** The Mysterious Bearded Man reaches out with both hands, clasping his strong hands tenderly over hers and the book.
- **Why:** A dramatic rescue followed by a tender, unresolved moment showcases the new alliance and leaves viewers wanting to see the conflict resolve.
- **Scores:** {'hook': 8.0, 'cliffhanger': 8.0, 'standalone': 8.0} | rules 0.35 | spoiler low | pattern: other
- **Retrieved for grounding:** -
- **What a new viewer lacks:** Juliana’s new husband’s protective gesture signals a turning point in her struggle.

### 6. E05-P1: Family Fall (25.0s, single)
- **Segments:** Ep5 00:04.00-00:29.00
- **Hook:** Lord Ashcroft’s cold command: “Miss Ashcroft.”
- **Cliffhanger:** From this moment, you are dead to the Ashcroft family.
- **Why:** A brutal family rejection cuts to a chilling ultimatum, leaving viewers craving the next step in Juliana’s fight.
- **Scores:** {'hook': 8.0, 'cliffhanger': 8.0, 'standalone': 8.0} | rules 0.3 | spoiler low | pattern: other
- **Retrieved for grounding:** -
- **What a new viewer lacks:** The ledger is a symbol of Juliana’s inheritance and her mother’s legacy.

### 7. E05-P2: Mud & Betrayal (22.4s, single)
- **Segments:** Ep5 00:46.60-01:09.00
- **Hook:** Lady Ashcroft’s venomous threat: “…that belongs to this family.”
- **Cliffhanger:** Juliana drops to her knees onto the wet courtyard pavement, oblivious to the dirt soaking through her white bridal gown.
- **Why:** The public shaming and the physical fall create a visceral hook, ending on a moment of vulnerability that begs for rescue.
- **Scores:** {'hook': 8.0, 'cliffhanger': 8.0, 'standalone': 8.0} | rules 0.3 | spoiler low | pattern: other
- **Retrieved for grounding:** -
- **What a new viewer lacks:** The ledger’s destruction is a public humiliation that fuels Juliana’s desperation.

### 8. E45-P1: The Unshackling & The Shock (37.5s, single)
- **Segments:** Ep45 00:53.80-01:31.30
- **Hook:** You poisoned my mother. You tortured my wife.
- **Cliffhanger:** No one will bow yet!
- **Why:** Starts with a brutal accusation that stops scrolling, ends with a bishop’s dramatic entrance, leaving viewers wondering how the marriage will be challenged.
- **Scores:** {'hook': 8.0, 'cliffhanger': 8.0, 'standalone': 8.0} | rules 0.5 | spoiler medium | pattern: other
- **Retrieved for grounding:** -
- **Fixes:** model repaired it after validator feedback: too long (103.3s > 60s)

### 9. E41-P1: Chain‑Break (43.5s, single)
- **Segments:** Ep41 00:17.30-01:00.80
- **Hook:** Juliana is marched forward, shackled, into the cathedral
- **Cliffhanger:** Juliana defiantly questions Catherine’s power
- **Why:** A single, punchy sequence that shows Juliana’s humiliation and her fiery retort, leaving viewers craving the fallout.
- **Scores:** {'hook': 8.0, 'cliffhanger': 8.0, 'standalone': 8.0} | rules 0.45 | spoiler medium | pattern: other
- **Retrieved for grounding:** -

### 10. E27-P1: Ring of Deception (44.7s, multi-moment)
- **Segments:** Ep27 00:44.20-00:51.50 + Ep27 01:17.80-01:32.80 + Ep27 02:02.80-02:25.20
- **Hook:** What is your husband's name?
- **Cliffhanger:** She secretly administers an unidentified substance to a helpless woman.
- **Why:** The clip opens with a shocking revelation about a family crest, then cuts to a dramatic confrontation where Juliana is framed for poisoning, leaving viewers desperate to know the truth.
- **Scores:** {'hook': 8.0, 'cliffhanger': 9.0, 'standalone': 8.0} | rules 0.525 | spoiler high | pattern: other
- **Retrieved for grounding:** -
- **What a new viewer lacks:** Why is the Dowager Duchess suspicious of Juliana?

### 11. E45-P2: Duke’s Declaration (6.2s, multi-moment)
- **Segments:** Ep45 00:21.80-00:24.50 + Ep45 01:11.00-01:14.50
- **Hook:** Alexander drops to one knee and drops the ducal cloak over Juliana
- **Cliffhanger:** The priest’s voice booms, "You are not Duchess of Ashburton."
- **Why:** It showcases a powerful moment of elevation followed by a sudden legal blow, keeping viewers hooked.
- **Scores:** {'hook': 8.0, 'cliffhanger': 9.0, 'standalone': 7.0} | rules 0.625 | spoiler medium | pattern: other
- **Retrieved for grounding:** -
- **What a new viewer lacks:** The viewer must understand the significance of the ducal cloak and the title of Duchess.
- **Fixes:** model repaired it after validator feedback: too long (117.5s > 60s)
- **FAILED CHECKS:** too short (6.2s < 20s)
