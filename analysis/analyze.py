"""Aggregate metrics from reference-game results into tidy CSVs + a stats summary."""
import json
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

RESULTS = Path(__file__).parent.parent / "results"
OUT = Path(__file__).parent

STOP = set("the a an of with on in at to and or it is that shape one like looks".split())


def content_words(text):
    return set(w for w in re.findall(r"[a-z']+", text.lower()) if w not in STOP)


def load():
    rows, probe_rows, lexicons = [], [], {}
    for f in sorted(RESULTS.glob("*.json")):
        if f.name.endswith("_transcripts.json"):
            continue
        g = json.loads(f.read_text())
        key = (g["condition"], g["game_seed"])
        for t in g["trials"]:
            rows.append({"condition": g["condition"], "seed": g["game_seed"], **{
                k: t[k] for k in ("round", "trial", "target", "n_words", "n_chars",
                                  "correct", "phase", "description")}, "audit": ";".join(t["audit"])})
        for probe_name, recs in (g.get("probes") or {}).items():
            if probe_name == "lexicon":
                lexicons[key] = recs
                continue
            for r in recs:
                probe_rows.append({"condition": g["condition"], "seed": g["game_seed"],
                                   "probe": probe_name, "target": r["target"],
                                   "message": r["message"], "correct": r["correct"]})
    return pd.DataFrame(rows), pd.DataFrame(probe_rows), lexicons


def lexical_stability(df):
    """Content-word overlap (Jaccard) between consecutive-round descriptions of same item."""
    recs = []
    for (cond, seed, target), grp in df.groupby(["condition", "seed", "target"]):
        grp = grp.sort_values("round")
        descs = list(zip(grp["round"], grp["description"]))
        for (r1, d1), (r2, d2) in zip(descs, descs[1:]):
            w1, w2 = content_words(d1), content_words(d2)
            if w1 | w2:
                recs.append({"condition": cond, "seed": seed, "target": target,
                             "round_pair": f"{r1}-{r2}", "round_to": r2,
                             "jaccard": len(w1 & w2) / len(w1 | w2)})
    return pd.DataFrame(recs)


def main():
    df, probes, lexicons = load()
    df.to_csv(OUT / "trials.csv", index=False)
    if len(probes):
        probes.to_csv(OUT / "probes.csv", index=False)
    stab = lexical_stability(df)
    stab.to_csv(OUT / "stability.csv", index=False)
    (OUT / "lexicons.json").write_text(json.dumps(
        {f"{c}_{s}": v for (c, s), v in lexicons.items()}, indent=1))

    print("=== trials per condition ===")
    print(df.groupby("condition").size())
    print("\n=== words per description, by condition x round ===")
    print(df.pivot_table(index="round", columns="condition", values="n_words").round(1))
    print("\n=== accuracy by condition x round ===")
    print(df.pivot_table(index="round", columns="condition", values="correct").round(2))
    print("\n=== lexical stability (jaccard, consecutive rounds) ===")
    print(stab.pivot_table(index="round_to", columns="condition", values="jaccard").round(2))
    if len(probes):
        print("\n=== probes ===")
        print(probes.groupby(["probe", "condition"])["correct"].agg(["mean", "count"]).round(2))
    print("\n=== audit flags ===")
    print(df[df["audit"] != ""].groupby(["condition", "audit"]).size() if (df["audit"] != "").any()
          else "none")


if __name__ == "__main__":
    main()
