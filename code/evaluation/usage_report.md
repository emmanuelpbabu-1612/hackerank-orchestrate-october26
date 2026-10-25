# Usage report — final full-dataset run

Run producing the submitted `output.csv`:

```text
python3 code/main.py --full
```

- 518/518 cases processed, one output row per `case_id`, deterministic.
- Wall time of a full run: ~16 s (single core, includes ingest + planning + gate).

## Model providers and names

| component | provider | model | used in final run? |
|---|---|---|---|
| request gate (NOT_APPLICABLE) | — | deterministic multilingual keyword/negation rules (`code/classify.py`) | yes |
| identity resolution, evidence parsing, planning | — | deterministic Python pipeline (`code/main.py`) | yes |
| optional LLM fallback for ambiguous gate texts | env-configured (`LLM_PROVIDER`/`LLM_MODEL`/`LLM_API_KEY`) | — | no (no API key present; 0 ambiguous texts in the dataset) |
| OCR for PNG evidence | — | `tesseract` CLI binary (system tool, not an LLM) | lite path if PNGs present |

## Model call counts / tokens / cost

| model | calls | input tokens | output tokens | est. cost (USD) |
|---|---|---|---|---|
| deterministic pipeline (no model) | 0 | 0 | 0 | $0.00 |
| optional LLM fallback | 0 | 0 | 0 | $0.00 |
| **total** | **0** | **0** | **0** | **$0.00** |

Average tokens per request: 0 (no model calls). Estimated per-request cost: $0.0000.

The runner is fully reproducible without any API access; the optional LLM path
(`LLM_*` environment variables, see `.env.example`) is a fallback exercised only
when the keyword classifier finds an ambiguous request text, and its results are
cached on disk in `code/evaluation/llm_cache.json`.
