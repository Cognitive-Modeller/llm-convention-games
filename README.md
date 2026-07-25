# LLM Convention Games

Iterated reference-game experiment (Clark & Wilkes-Gibbs tangram paradigm, text-only)
between two `gemini-2.5-flash` agents, testing claims from Gregoromichelaki & Mills
(2025), *Process and Dynamics in AI and Language Use*, Topics in Cognitive Science:
symbols as interaction-bound constraints, "ungrounding" of conventions, partner-specificity.

**Report:** open `analysis/report.html` (self-contained — charts, probes, discussion, limitations).

## Headline results (run 3, the clean run)

- All 5 shared-history dyads reach 100% matcher accuracy by round 6; no-history control stays ~50%.
- Partner swap after round 6: accuracy 100% → 72% (Fisher p = 0.0004), recovers via feedback.
- Bare final labels: 39/40 with the 6-round partner vs 25/40 with a fresh agent (p = 1.2e-4).
  Same frozen weights on both sides — the 36-point gap lives entirely in the shared transcript.
- Negation over established labels ("neither X nor Y", 3-shape display): 20/20.
- Unlike humans: no compression from verbose to terse. Descriptions start short,
  lengthen on failure, and **freeze** (consecutive-round Jaccard → 1.0 vs 0.10 control).

## Files

| Path | What |
|---|---|
| `stimuli.py` | 8 center-normalized abstract ASCII shapes (seeded generator) |
| `game.py` | Game engine: director/matcher agents, swap conditions, ungrounding probes |
| `run_all.py` | Full grid: 3× baseline (overt swap), 2× covert swap, 2× no-history |
| `analysis/analyze.py` | Tidy CSVs + stats summary |
| `analysis/make_report.py` | Injects data + `report_texts.json` into `report_template.html` |
| `results/` | Run-3 per-trial JSON + full agent transcripts |
| `results/run1_probebug/` | Archived run 1 (stale probe-display artifact + strict-parser artifact) |
| `results/run2_parserbug/` | Archived partial run 2 (probe fix in, parser fix not yet) |

## Instrument lessons (the two archived bugs)

1. **Strict answer parsing poisons interaction experiments.** The matcher drifts into
   `$\boxed{B}$` / "final answer is B" formats; scoring those as wrong creates false
   negative feedback → the director elaborates → the matcher drifts further (one run-1
   game spiraled to 47-word descriptions and 19% accuracy). Fix: tolerant parser + one
   instrument-level format re-ask.
2. **Letter-remapped displays must be re-shown at probe time.** A matcher probed after
   the game answered consistently under a stale round's letter mapping — errors formed
   clean permutations, misread as comprehension failure.

## Rerun

```bash
pip install google-genai pandas scipy
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=<your-gcp-project>   # any project with Vertex AI enabled
python3 run_all.py        # skips games whose results JSON already exists
cd analysis && python3 analyze.py && python3 make_report.py
```

No credentials live in this repo: auth is Application Default Credentials, and the
GCP project is read from `GOOGLE_CLOUD_PROJECT`. ~1,600 model calls ≈ US$5.
