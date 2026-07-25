"""Generate abstract tangram-like ASCII shapes for reference games.

Each shape = 2-3 random-walk strokes on a 10x10 grid, seeded for
reproducibility. Shapes are meant to be hard to name instantly but
discriminable with effort (like tangram figures).
"""
import random

GRID = 10


def _stroke(rng, grid, start, length):
    r, c = start
    grid[r][c] = "#"
    heading = rng.choice([(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)])
    for _ in range(length):
        if rng.random() < 0.3:  # turn
            heading = rng.choice([(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)])
        nr, nc = r + heading[0], c + heading[1]
        if 0 <= nr < GRID and 0 <= nc < GRID:
            r, c = nr, nc
            grid[r][c] = "#"
        else:
            heading = (-heading[0], -heading[1])
    return r, c


def make_shape(seed):
    rng = random.Random(seed)
    grid = [["." for _ in range(GRID)] for _ in range(GRID)]
    n_strokes = rng.choice([2, 3])
    start = (rng.randrange(2, 8), rng.randrange(2, 8))
    for _ in range(n_strokes):
        end = _stroke(rng, grid, start, rng.randrange(6, 12))
        # next stroke starts near where previous ended (connected figure)
        start = (max(0, min(GRID - 1, end[0] + rng.randrange(-2, 3))),
                 max(0, min(GRID - 1, end[1] + rng.randrange(-2, 3))))
    return "\n".join("".join(row) for row in grid)


def density(shape):
    return shape.count("#")


if __name__ == "__main__":
    for seed in range(40):
        s = make_shape(seed)
        d = density(s)
        if 12 <= d <= 30:
            print(f"=== seed {seed} (cells={d}) ===")
            print(s)
            print()


def center(shape):
    rows = [list(r) for r in shape.split("\n")]
    cells = [(r, c) for r in range(GRID) for c in range(GRID) if rows[r][c] == "#"]
    rmin, rmax = min(r for r, _ in cells), max(r for r, _ in cells)
    cmin, cmax = min(c for _, c in cells), max(c for _, c in cells)
    dr = (GRID - (rmax - rmin + 1)) // 2 - rmin
    dc = (GRID - (cmax - cmin + 1)) // 2 - cmin
    grid = [["." for _ in range(GRID)] for _ in range(GRID)]
    for r, c in cells:
        grid[r + dr][c + dc] = "#"
    return "\n".join("".join(row) for row in grid)


CHOSEN_SEEDS = [1, 9, 11, 16, 25, 34, 36, 37]
SHAPES = {f"S{i+1}": center(make_shape(s)) for i, s in enumerate(CHOSEN_SEEDS)}
