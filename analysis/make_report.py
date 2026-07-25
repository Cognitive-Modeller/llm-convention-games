"""Build report.html: inject computed DATA into report_template.html."""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from stimuli import SHAPES  # noqa: E402

from analyze import load, lexical_stability  # noqa: E402

OUT = Path(__file__).parent


def curves(df, stab):
    out = {}
    for cond, grp in df.groupby("condition"):
        by_round = grp.groupby("round").agg(words=("n_words", "mean"), acc=("correct", "mean"))
        st = stab[stab.condition == cond].groupby("round_to")["jaccard"].mean()
        out[cond] = [
            {"round": int(r), "words": round(row.words, 2), "acc": round(row.acc, 3),
             "jaccard": round(float(st.get(r)), 3) if r in st.index else None}
            for r, row in by_round.iterrows()
        ]
    return out


def main(texts_path="report_texts.json"):
    df, probes, lexicons = load()
    stab = lexical_stability(df)
    texts = json.loads((OUT / texts_path).read_text())

    probe_pool = probes.groupby("probe")["correct"].agg(["mean", "count"])
    probe_bars = [
        {"name": "Bare label →\n6-round partner", "slot": "--s1",
         "v": round(probe_pool.loc["bare_label_partner", "mean"], 3),
         "n": int(probe_pool.loc["bare_label_partner", "count"])},
        {"name": "Negation over labels →\n6-round partner", "slot": "--s1",
         "v": round(probe_pool.loc["negation_partner", "mean"], 3),
         "n": int(probe_pool.loc["negation_partner", "count"])},
        {"name": "Bare label →\nfresh agent, no history", "slot": "--s2",
         "v": round(probe_pool.loc["bare_label_fresh", "mean"], 3),
         "n": int(probe_pool.loc["bare_label_fresh", "count"])},
    ]

    lex = lexicons[tuple(texts["specimen_lexicon"])]
    data = {
        "stats": texts["stats"],
        "shapes": {sid: {"grid": SHAPES[sid], "label": lex.get(sid, "")} for sid in SHAPES},
        "curves": curves(df, stab),
        "words_ymax": float(df.groupby(["condition", "round"])["n_words"].mean().max()) * 1.15,
        "words_yticks": texts["words_yticks"],
        "probes": probe_bars,
        "probe_text": texts["probe_text"],
        "trajectory": texts["trajectory"],
        "discussion": texts["discussion"],
        "limitations": texts["limitations"],
        "repro": texts["repro"],
    }
    tpl = (OUT / "report_template.html").read_text()
    html = tpl.replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
    (OUT / "report.html").write_text(html)
    print("wrote", OUT / "report.html", len(html), "bytes")


if __name__ == "__main__":
    main()
