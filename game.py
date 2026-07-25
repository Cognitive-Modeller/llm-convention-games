"""Iterated reference game between two LLM agents (director / matcher).

Paradigm: Clark & Wilkes-Gibbs (1986) / Hawkins et al. (2020) tangram games,
adapted to text-only ASCII shapes and LLM agents. Tests claims from
Gregoromichelaki & Mills (2025): symbols-as-constraints, partner-specificity,
"ungrounding" of conventions formed in interaction.

Conditions:
  baseline      6 rounds with matcher M1, then rounds 7-8 with fresh M2,
                director TOLD about the swap (overt).
  covert        same, but director NOT told about the swap.
  no_history    6 rounds, fresh director+matcher every round (no shared past).
"""
import json
import os
import random
import re
import time
from pathlib import Path

from google import genai
from google.genai import types

from stimuli import SHAPES

MODEL = "gemini-2.5-flash"
# Vertex AI via Application Default Credentials; set your own project:
#   export GOOGLE_CLOUD_PROJECT=<your-gcp-project>
PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
RESULTS = Path(__file__).parent / "results"
LETTERS = "ABCDEFGH"

client = genai.Client(vertexai=True, project=PROJECT, location="global")

DIRECTOR_SYS = """You are playing a communication game with a partner, over text.

There are 8 abstract shapes, each drawn on a 10x10 grid of '#' (filled) and '.' (empty) cells. You and your partner see the SAME 8 shapes, but in a different random order on your partner's screen, so ordering is useless for communication.

On each trial, one shape is secretly assigned to you as the target. Send your partner a message so they can pick out the target.

Rules:
- Do NOT reproduce the grid, use row/column numbers, cell coordinates, or counts of cells.
- Do NOT refer to the position of a shape in the lineup.
- Describe the shape in natural language only.
- Every word costs you: keep each message as brief as you can while still being confident your partner will pick correctly. Exploit everything you and your partner have already established together.

After each trial you will learn whether your partner chose correctly.

Reply with ONLY the message to your partner — no preamble, no quotes."""

MATCHER_SYS = """You are playing a communication game with a partner, over text.

There are 8 abstract shapes, each drawn on a 10x10 grid of '#' (filled) and '.' (empty) cells. You and your partner see the SAME 8 shapes, but the letter labels (A-H) and their order exist only on YOUR screen and get reshuffled between rounds — your partner never sees them.

On each trial, your partner sends a message describing one target shape. Work out which shape they mean.

After each trial you will learn whether you chose correctly.

End your reply with exactly one line in this format:
ANSWER: <letter>"""


def call(system, history, temperature, thinking_budget=1024, max_retries=6):
    contents = [
        types.Content(role=h["role"], parts=[types.Part.from_text(text=h["text"])])
        for h in history
    ]
    for attempt in range(max_retries):
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=temperature,
                    thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
                ),
            )
            if resp.text:
                return resp.text.strip()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt + random.random())
    raise RuntimeError("empty response after retries")


class Agent:
    def __init__(self, system, temperature):
        self.system = system
        self.temperature = temperature
        self.history = []

    def tell(self, text):
        self.history.append({"role": "user", "text": text})

    def ask(self, text, thinking_budget=1024):
        self.tell(text)
        reply = call(self.system, self.history, self.temperature, thinking_budget)
        self.history.append({"role": "model", "text": reply})
        return reply


def shapes_block(order, letters=None):
    parts = []
    for i, sid in enumerate(order):
        header = f"Shape {letters[i]}:" if letters else ""
        parts.append(f"{header}\n{SHAPES[sid]}" if letters else SHAPES[sid])
    return "\n\n".join(parts)


def new_director(rng):
    d = Agent(DIRECTOR_SYS, temperature=0.7)
    order = list(SHAPES)  # canonical order; no labels shown
    d.tell("Here are the 8 shapes in the game (in no particular order):\n\n"
           + shapes_block(order)
           + "\n\nThe game starts now.")
    return d


def new_matcher(rng):
    m = Agent(MATCHER_SYS, temperature=0.2)
    m.mapping = None
    return m


def reshuffle_matcher(m, rng, round_no):
    order = list(SHAPES)
    rng.shuffle(order)
    m.mapping = dict(zip(LETTERS, order))  # letter -> shape id
    m.tell(f"Round {round_no}. The shapes on your screen (labels reshuffled):\n\n"
           + shapes_block(order, LETTERS))


def parse_answer(reply):
    # models drift out of the ANSWER: format into e.g. $\boxed{B}$ or
    # "The final answer is B" — accept those rather than scoring a
    # correct choice as a miss (run-1 lesson: strict parsing poisons the
    # game via false "wrong" feedback)
    for pat in (r"ANSWER:\s*\**\s*([A-H])\b",
                r"\\boxed\{\s*\**\s*(?:Shape\s*)?([A-H])\s*\**\s*\}",
                r"(?:final answer|answer)\s*(?:is|:)\s*\**\s*(?:Shape\s*)?([A-H])\b"):
        matches = re.findall(pat, reply, re.IGNORECASE)
        if matches:
            return matches[-1].upper()
    return None


def audit_flags(desc):
    flags = []
    if "#" in desc or "..." in desc and desc.count(".") > 8:
        flags.append("grid_chars")
    if re.search(r"\b(row|column|coordinate)s?\b\s*\d|\b\d+\s*(st|nd|rd|th)\s+(row|column)", desc, re.I):
        flags.append("coordinates")
    return flags


def run_trial(director, matcher, target, trial_no, round_no, rng):
    desc = director.ask(f"Trial {trial_no} (round {round_no}). Your target:\n\n{SHAPES[target]}\n\nMessage to partner:",
                        thinking_budget=512)
    reply = matcher.ask(f'Your partner says: "{desc}"\n\nWhich shape do they mean?')
    letter = parse_answer(reply)
    if letter is None:  # instrument-level re-ask, not part of the game
        reply = matcher.ask("Reply with exactly one line: ANSWER: <letter>")
        letter = parse_answer(reply)
    chosen = matcher.mapping.get(letter) if letter else None
    correct = chosen == target
    target_letter = next(l for l, s in matcher.mapping.items() if s == target)
    matcher.tell("Correct!" if correct else f"Wrong — the target was shape {target_letter}.")
    director.tell("Your partner chose correctly." if correct
                  else "Your partner chose the WRONG shape.")
    return {
        "round": round_no, "trial": trial_no, "target": target,
        "description": desc, "n_words": len(desc.split()), "n_chars": len(desc),
        "matcher_letter": letter, "matcher_choice": chosen, "correct": correct,
        "audit": audit_flags(desc),
    }


def run_game(condition, game_seed, n_rounds=6, swap_rounds=2, verbose=False):
    rng = random.Random(game_seed)
    trials, trial_no = [], 0
    director = new_director(rng)
    matcher = new_matcher(rng)

    matcher_m1 = matcher
    total_rounds = n_rounds + (swap_rounds if condition in ("baseline", "covert") else 0)
    for rnd in range(1, total_rounds + 1):
        if condition == "no_history" and rnd > 1:
            director, matcher = new_director(rng), new_matcher(rng)
        if condition in ("baseline", "covert") and rnd == n_rounds + 1:
            matcher = new_matcher(rng)  # fresh partner, no shared history
            if condition == "baseline":
                director.tell("NOTE: your partner has left and been replaced by a NEW partner. "
                              "The new partner sees the same 8 shapes but has NOT seen any of "
                              "your previous conversation.")
        reshuffle_matcher(matcher, rng, rnd)
        targets = list(SHAPES)
        rng.shuffle(targets)
        for target in targets:
            trial_no += 1
            rec = run_trial(director, matcher, target, trial_no, rnd, rng)
            rec["phase"] = "pre_swap" if rnd <= n_rounds else "post_swap"
            trials.append(rec)
            if verbose:
                print(f"[{condition}/{game_seed}] r{rnd} {target} "
                      f"{'OK ' if rec['correct'] else 'MISS'} ({rec['n_words']}w) {rec['description'][:90]!r}")

    game = {"condition": condition, "game_seed": game_seed, "model": MODEL,
            "n_rounds": n_rounds, "trials": trials}
    if condition in ("baseline", "covert"):
        game["probes"] = run_probes(director, matcher_m1, rng, verbose)
    out = RESULTS / f"{condition}_seed{game_seed}.json"
    out.write_text(json.dumps(game, indent=1))
    # full transcripts for qualitative analysis
    (RESULTS / f"{condition}_seed{game_seed}_transcripts.json").write_text(json.dumps(
        {"director": director.history, "matcher_m1": matcher_m1.history,
         "matcher_final": matcher.history}, indent=1))
    return game


# ---------------------------------------------------------------- probes ----

def elicit_lexicon(director):
    order = list(SHAPES)
    prompt = ("Final task. Below are the 8 shapes again, numbered 1-8 FOR THIS QUESTION ONLY. "
              "For each, give the short label/name you would now use with your partner "
              "to refer to it. Reply with ONLY a JSON object mapping the numbers to labels, "
              'e.g. {"1": "the ladder", ...}\n\n'
              + "\n\n".join(f"Shape {i+1}:\n{SHAPES[s]}" for i, s in enumerate(order)))
    reply = director.ask(prompt)
    m = re.search(r"\{.*\}", reply, re.DOTALL)
    labels = json.loads(m.group(0))
    return {order[int(k) - 1]: v for k, v in labels.items()}


def label_trial(matcher, message, target, rng, restrict=None):
    """One probe trial through a matcher. restrict = list of letters to consider."""
    scope = (f"For this special trial consider ONLY shapes {', '.join(restrict)}. "
             if restrict else "")
    reply = matcher.ask(f'{scope}Your partner says: "{message}"\n\nWhich shape do they mean?')
    letter = parse_answer(reply)
    if letter is None:
        reply = matcher.ask("Reply with exactly one line: ANSWER: <letter>")
        letter = parse_answer(reply)
    chosen = matcher.mapping.get(letter) if letter else None
    matcher.tell("OK.")  # no correctness feedback during probes
    return {"message": message, "target": target, "chosen": chosen,
            "correct": chosen == target}


def run_probes(director, matcher_m1, rng, verbose=False):
    """matcher_m1 = the original 6-round partner (full shared history)."""
    probes = {}
    try:
        lex = elicit_lexicon(director)
    except Exception:
        lex = elicit_lexicon(director)  # one retry on malformed JSON
    probes["lexicon"] = lex
    if verbose:
        print("LEXICON:", json.dumps(lex, indent=1))

    # Refresh M1's display so its letter answers use a current frame —
    # without this, M1 may answer under a stale round's letter mapping
    # (observed as clean permutations in run 1), which is a measurement
    # artifact, not a comprehension failure. The fresh matcher gets its
    # display immediately before probing, so this keeps the two arms matched.
    reshuffle_matcher(matcher_m1, rng, round_no=7)

    # P-partner: bare final labels -> M1 (shares the 6-round history)
    probes["bare_label_partner"] = [
        label_trial(matcher_m1, lex[s], s, rng) for s in SHAPES
    ]

    # P-neg: negation over labels, restricted 3-shape display, M1
    neg = []
    ids = list(SHAPES)
    for _ in range(4):
        a, b, c = rng.sample(ids, 3)
        letters = sorted(next(l for l, s in matcher_m1.mapping.items() if s == x) for x in (a, b, c))
        msg = f"It is the one that is NEITHER {lex[a]} NOR {lex[b]}."
        neg.append(label_trial(matcher_m1, msg, c, rng, restrict=letters))
    probes["negation_partner"] = neg

    # P-fresh: bare final labels -> completely fresh matcher (no history at all)
    fresh = new_matcher(rng)
    reshuffle_matcher(fresh, rng, round_no=1)
    probes["bare_label_fresh"] = [
        label_trial(fresh, lex[s], s, rng) for s in SHAPES
    ]
    return probes


if __name__ == "__main__":
    import sys
    cond = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 101
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    g = run_game(cond, seed, n_rounds=rounds, verbose=True)
    acc = sum(t["correct"] for t in g["trials"]) / len(g["trials"])
    print(f"\nDone: {len(g['trials'])} trials, overall accuracy {acc:.2f}")
