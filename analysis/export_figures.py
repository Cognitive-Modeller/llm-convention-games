"""Export report.html figures as theme-aware PNGs for the README.

For each figure: wrap report.html with CSS that shows only that element,
screenshot with headless Chrome at 2x, autocrop background margins.
"""
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
FIGURES = HERE.parent / "figures"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# figure id -> (css selector of the block to keep, window width)
FIGS = {
    "specimens": (".strip", 1240),
    "words": ("#chart-words", 900),
    "accuracy": ("#chart-acc", 900),
    "stability": ("#chart-stab", 900),
    "probes": ("#chart-probe", 900),
}

HIDE_CSS = """
<style>
  main > * { display: none !important; }
  main > *:has(%(sel)s) { display: block !important; }
  main > %(sel)s { display: %(disp)s !important; }
  .card { border: none !important; background: var(--page) !important; }
  .legend { justify-content: flex-start; }
  body { padding: 10px !important; }
  .fig-title, .fig-sub { display: none; }
</style>
"""


def autocrop(path, bg_tolerance=8):
    im = Image.open(path).convert("RGB")
    bg = im.getpixel((2, 2))
    diff = Image.eval(
        Image.merge("RGB", [
            im.getchannel(i).point(lambda p, c=bg[i]: 255 if abs(p - c) > bg_tolerance else 0)
            for i in range(3)
        ]).convert("L"),
        lambda p: 255 if p else 0,
    )
    box = diff.getbbox()
    if box:
        pad = 16
        box = (max(0, box[0] - pad), max(0, box[1] - pad),
               min(im.width, box[2] + pad), min(im.height, box[3] + pad))
        im.crop(box).save(path)


def shoot(name, sel, width, dark):
    html = (HERE / "report.html").read_text()
    inject = HIDE_CSS % {"sel": sel, "disp": "flex" if sel == ".strip" else "block"}
    if dark:
        inject += '<script>document.documentElement.dataset.theme="dark"</script>'
    html = html.replace("<style>", inject + "<style>", 1)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
        tmp = f.name
    out = FIGURES / f"{name}_{'dark' if dark else 'light'}.png"
    subprocess.run([
        CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=2",
        f"--screenshot={out}", f"--window-size={width},900", f"file://{tmp}",
    ], check=True, capture_output=True)
    autocrop(out)
    print(out.name, Image.open(out).size)


if __name__ == "__main__":
    FIGURES.mkdir(exist_ok=True)
    for name, (sel, width) in FIGS.items():
        for dark in (False, True):
            shoot(name, sel, width, dark)
