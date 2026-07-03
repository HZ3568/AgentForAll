# GAIA Evaluation

This project can run GAIA validation tasks through the normal CodeAgent-Harness loop.

## Run

Smoke test:

```powershell
python -m codeagent.evaluation.gaia.run_eval --level 1 --max-samples 5
```

Strict evidence mode:

```powershell
python -m codeagent.evaluation.gaia.run_eval --level 1 --max-samples 5 --gaia-eval-mode strict
```

Dataset-only check:

```powershell
python -m codeagent.evaluation.gaia.run_eval --level 1 --dataset-only
```

## Search API

`config.yaml` is not required. Put the provider API key in `.env`; the runtime auto-selects the first available provider in this order:

1. `BRAVE_SEARCH_API_KEY` -> `brave`
2. `TAVILY_API_KEY` -> `tavily`
3. `SERPAPI_API_KEY` -> `serpapi` (reserved)
4. `BING_SEARCH_API_KEY` -> `bing` (reserved)

Example `.env`:

```env
BRAVE_SEARCH_API_KEY=your_key_here
```

You can explicitly choose a provider with either variable:

```env
WEB_SEARCH_PROVIDER=brave
# or
CODEAGENT_WEB_SEARCH_PROVIDER=brave
```

Optional tuning:

```env
WEB_SEARCH_TIMEOUT_SECONDS=20
WEB_SEARCH_MAX_RESULTS=5
```

`config.yaml` remains an optional advanced override:

```yaml
web_search:
  provider: brave
  timeout_seconds: 20
  max_results: 5
```

Supported provider values:

- `brave`: uses `BRAVE_SEARCH_API_KEY`
- `tavily`: uses `TAVILY_API_KEY`
- `serpapi`: reserved
- `bing`: reserved
- `duckduckgo`: explicit fallback only; not recommended because it often returns bot challenges
- `disabled`: no search provider is available or search was explicitly disabled

Provider API key variables:

```env
BRAVE_SEARCH_API_KEY=
TAVILY_API_KEY=
SERPAPI_API_KEY=
BING_SEARCH_API_KEY=
```

If a provider is configured but its key is missing, `web_search` returns `ok=false` with `error_type=missing_api_key`.

## Strict Mode

`--gaia-eval-mode strict` injects GAIA-specific instructions:

- Do not answer from vague memory.
- Final answers must be grounded in observed tool output.
- `todo_write` is not evidence.
- If evidence is unavailable after relevant tools are tried, return `UNRESOLVED`.
- Temporary files must be written inside the per-sample scratch directory.

The evaluator also enforces this after the run: if `evidence_count == 0`, the sample is marked:

```json
{
  "status": "unresolved",
  "failure_type": "insufficient_evidence",
  "prediction": "UNRESOLVED"
}
```

## Supported File Types

Use structured tools instead of `read_file` for binary or structured files:

- Text: `read_file`, `search_text`
- CSV/XLS/XLSX: `read_spreadsheet`
- PDF text: `extract_pdf_text` or `pdf_extract`
- PDF tables: `extract_pdf_tables`
- Audio: `transcribe_audio` with optional `faster-whisper`
- Images: `ocr_image` with optional `pytesseract`

Optional heavy dependencies are not installed by default:

```text
faster-whisper
pytesseract
paddleocr
```

When optional dependencies are missing, tools return explicit errors such as `missing_audio_dependency` or `missing_ocr_dependency`.

## Outputs

Aggregate outputs:

```text
outputs/gaia_results.json
outputs/gaia_submission.jsonl
outputs/gaia_failure_summary.json
```

Per-sample outputs:

```text
outputs/gaia_runs/{task_id}/result.json
outputs/gaia_runs/{task_id}/trace.json
outputs/gaia_runs/{task_id}/scratch/
```

Each sample result includes:

- `status`
- `failure_type`
- `tools_used`
- `tool_errors`
- `evidence`
- `evidence_count`
- `scratch_dir`

## Failure Types

Common values:

- `web_search_blocked`
- `web_search_empty`
- `fetch_failed`
- `file_parse_failed`
- `audio_transcription_failed`
- `ocr_failed`
- `shell_command_failed`
- `insufficient_evidence`
- `answer_format_error`
- `reasoning_error`
- `timeout`
- `unknown`

## Troubleshooting

Search API key missing:

- Set the matching environment variable, for example `BRAVE_SEARCH_API_KEY`.
- If you explicitly set `WEB_SEARCH_PROVIDER` or `CODEAGENT_WEB_SEARCH_PROVIDER`, make sure the matching API key also exists.

HTTP 403 / 429:

- The provider blocked or rate-limited the request.
- Try another provider or wait for quota reset.

DuckDuckGo challenge:

- DuckDuckGo HTML is not the default provider and often returns bot challenges.
- Configure Brave or Tavily for stable runs.

OCR / Whisper missing:

- Install optional dependencies only when needed.
- The tool will return `missing_ocr_dependency` or `missing_audio_dependency` instead of crashing.

Windows shell compatibility:

- The runtime tells the agent the current OS and shell.
- GAIA mode prefers `list_dir`, `find_files`, `search_text`, and structured file tools.
- Obvious Linux-only commands such as `xargs`, `grep -R`, `find . -type f`, `sed -i`, and `awk` are blocked on Windows.
