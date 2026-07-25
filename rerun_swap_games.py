"""Re-run the 5 swap games with the fixed probe protocol (display refresh for M1)."""
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from game import run_game

GRID = [("baseline", s) for s in (101, 102, 103)] + [("covert", s) for s in (201, 202)]


def one(cond, seed):
    try:
        from game import RESULTS
        if (RESULTS / f"{cond}_seed{seed}.json").exists():
            return f"{cond}/seed{seed}: already done, skipped"
        g = run_game(cond, seed, n_rounds=6, verbose=False)
        acc = sum(t["correct"] for t in g["trials"]) / len(g["trials"])
        return f"{cond}/seed{seed}: acc {acc:.2f}"
    except Exception:
        return f"{cond}/seed{seed} FAILED:\n{traceback.format_exc()}"


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=5) as ex:
        for f in as_completed({ex.submit(one, c, s) for c, s in GRID}):
            print(f.result(), flush=True)
    print("RERUN DONE")
