
# Content Enrichment Pipeline (v2)

This project enriches Markdown articles with a hero image, in-context image/video, and two contextual hyperlinks using LLM-generated anchor text. Version 2 integrates hyperlinks inline within paragraphs, adds AI-agent QA using structured output with automatic failover, introduces uv-based dependency management, Celery + Redis task queue, a minimal FastAPI service, and optional flow state persistence.

## How it works
- **Data retrieval:** Loads article, keywords, brand rules, and queries images/videos (`media.db`) plus resources (`links.db`).
- **Shortlisting:** Scores and shortlists media and links by keyword/section overlap and asset authority.
- **LLM selection:** Prompts an LLM to choose a hero image, in-context item, and two links with descriptive anchors using target keywords; returns strict JSON.
- **Fallback:** If offline or API error, uses top-ranked candidates and deterministic safe anchors.
- **Rendering:** Hero after H1; in-context media under a chosen section; hyperlinks are inserted inline within sentences.
- **QA:** AI-agent QA via structured output using Instructor with automatic failover to non-AI QA.


## Setup (uv)
1. Windows or Macos/Linux `python scripts/install_uv.py`
2. `uv venv`
3. Windows: `.venv\Scripts\activate` use `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` if error message on PowerShell |
 macOS/Linux: `source .venv/bin/activate`
4. `uv sync`
5. Set `OPENROUTER_API_KEY` and optional `OPENROUTER_MODEL` in env or `config/.env`.
## Run (CLI)
- Example:  
  `uv run python run.py --article_path "data/articles/article_1.md" --keywords_path "data/keywords/keywords_1.txt"`
- Add `--offline` to disable LLM selection.
- Add `--qa_mode ai|fallback|auto` to choose QA mode; default `auto`.
- Output: `outputs/enriched_<article_name>.md` unless `--out_path` is set.

- For tests replace `article_1.md` and `keywords_1.txt` with your own files, use `data/articles/<your_article>.md` and `data/keywords/<your_keyword>.txt`.

Alternatively, run `python scripts/run.py` with the same arguments.

## Run (Docker) Windows 
- Start services:  
  `docker compose up -d`
- One‑liner to create payload and POST (API ENDPOINT 1 POST):  
  `$Payload = @{ article_path = "/app/data/articles/article_1.md"; keywords_path = "/app/data/keywords/keywords_1.txt"; offline = $false; qa_mode = "ai" } | ConvertTo-Json -Compress; Invoke-RestMethod -Uri http://localhost:8000/tasks -Method POST -ContentType 'application/json' -Body $Payload`
- Poll status (paste the task id you received) (API ENDPOINT 2 GET):  
  `Invoke-RestMethod -Uri http://localhost:8000/tasks/0b64aa2b-14cc-42fd-b70c-8b03df756c750b64aa2b-14cc-42fd-b70c-8b03df756c75 -Method GET`
- Auto‑copy on success (5s countdown) if Not run the command below:
  - `$tid = "<task_id>"`
  - `$resp = Invoke-RestMethod -Uri ("http://localhost:8000/tasks/" + $tid) -Method GET`
  - `if ($resp.state -eq "SUCCESS" -and $resp.result) { Write-Host "Success. Copying in 5s..."; Start-Sleep -Seconds 5; $fname = Split-Path $resp.result -Leaf; docker cp take_home_assignment_ce_v3-web-1:$resp.result ("outputs/" + $fname); Write-Host ("Copied to outputs/" + $fname) }`
- Example output:  
  `task_id  state    result`  
  `<uuid>    SUCCESS  /app/outputs/enriched_article_1.md`
- Notes:  
  - Use container paths for `article_path` and `keywords_path` (prefixed with `/app/`).  
  - Toggle `offline` and `qa_mode` (`ai|auto|fallback`).
  - Inspect worker logs: `docker compose logs worker --tail 200`.

## Run (Docker) macOS 

### For jq based commands make sure you have jq tools installed otherwise use no jq commands:

- Start services:  
  `docker compose up -d`
- One‑liner to POST task:  
  `curl -s -X POST http://localhost:8000/tasks -H 'Content-Type: application/json' -d '{"article_path":"/app/data/articles/article_1.md","keywords_path":"/app/data/keywords/keywords_1.txt","offline":false,"qa_mode":"ai"}'`
- Get task id (jq):  
  `TASK_ID=$(curl -s -X POST http://localhost:8000/tasks -H 'Content-Type: application/json' -d '{"article_path":"/app/data/articles/article_1.md","keywords_path":"/app/data/keywords/keywords_1.txt","offline":false,"qa_mode":"ai"}' | jq -r '.task_id')`
- Get task id (no jq):  
  `TASK_ID=$(curl -s -X POST http://localhost:8000/tasks -H 'Content-Type: application/json' -d '{"article_path":"/app/data/articles/article_1.md","keywords_path":"/app/data/keywords/keywords_1.txt","offline":false,"qa_mode":"ai"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["task_id"])')`
- Poll status:  
  `curl -s http://localhost:8000/tasks/$TASK_ID`
- Auto‑copy on success if Not run the command below (no jq):
  - `JSON=$(curl -s http://localhost:8000/tasks/$TASK_ID)`
  - `STATE=$(echo "$JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["state"])')`
  - `RESULT=$(echo "$JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["result"])')`
  - `if [ "$STATE" = "SUCCESS" ] && [ -n "$RESULT" ]; then echo "Success. Copying in 5s..."; sleep 5; FNAME=$(basename "$RESULT"); docker cp take_home_assignment_ce_v3-web-1:"$RESULT" "outputs/$FNAME"; echo "Copied to outputs/$FNAME"; fi`
- Notes:  
  - Use container paths `/app/...`.  
  - Toggle `offline` and `qa_mode`.  
  - Logs: `docker compose logs worker --tail 200`.

## FastAPI + Celery
- Start via Docker Compose: `docker compose up`
- `POST /tasks` with `{ "article_path": "...", "keywords_path": "..." }` to enqueue
- `GET /tasks/{id}` to check status

## Flows & Persistence
- Enable flow persistence by setting `USE_FLOW=1`. State is recorded via CrewAI + Redis using keys `flow:<run_id>:<step>`.
- Configure Redis DB with `FLOW_REDIS_URL` (Compose sets `redis://redis:6379/2`).
- Set `FLOW_RUN_ID` to customize the run identifier; default is `default`.

## Flow Inspection
- List flow keys in Redis:  
  `docker exec take_home_assignment_ce_v3-redis-1 redis-cli -n 2 keys "flow:*"`
- View a specific step:  
  `docker exec take_home_assignment_ce_v3-redis-1 redis-cli -n 2 get flow:default:profile`  
  `docker exec take_home_assignment_ce_v3-redis-1 redis-cli -n 2 get flow:default:shortlist`  
  `docker exec take_home_assignment_ce_v3-redis-1 redis-cli -n 2 get flow:default:render`

## API vs CLI Output
- Generate via CLI:  
  `uv run python run.py --article_path "data/articles/article_1.md" --keywords_path "data/keywords/keywords_1.txt"`
- Generate via API (container paths):  
  PowerShell:  
  `$Payload = @{ article_path = "/app/data/articles/article_1.md"; keywords_path = "/app/data/keywords/keywords_1.txt"; offline = $false; qa_mode = "ai" } | ConvertTo-Json; Invoke-RestMethod -Uri http://localhost:8000/tasks -Method POST -ContentType 'application/json' -Body $Payload`
  `Invoke-RestMethod -Uri http://localhost:8000/tasks/<task_id> -Method GET`
- Copy API output to host:  
  `docker cp take_home_assignment_ce_v3-web-1:/app/outputs/enriched_article_1.md outputs/api_enriched_article_1.md`
- Diff on Windows:  
  `fc outputs\enriched_article_1.md outputs\api_enriched_article_1.md`

## Tests
- Run all tests:  
  `uv run pytest -q`
- Run a specific test file:  
  `uv run pytest -q tests/test_renderer_em_dash.py`
- Verbose output:  
  `uv run pytest -vv`
- Without uv (activated venv) – Windows:  
  `.venv\Scripts\activate; pytest -q`
- Without uv (activated venv) – macOS/Linux:  
  `source .venv/bin/activate; pytest -q`

## External libraries used
- `httpx`
- `pydantic`
- `structlog`
- `python-dotenv`
- `instructor`, `openai`
- `fastapi`, `uvicorn`
- `celery`, `redis`
- `crewai`


## Environment Variables

The project uses environment variables for configuration. Create a `config/.env` file (see example below):

### API Keys
- `OPENROUTER_API_KEY` - Your OpenRouter API key for LLM access
- `OPENAI_API_KEY` - Same as OPENROUTER_API_KEY (used by CrewAI)

### LLM Configuration
- `OPENROUTER_MODEL` - OpenRouter model ID (default: `openai/gpt-4o-mini`)
- `LLM_DEBUG` - Enable detailed LLM request/response logging (`0` or `1`)
- `LLM_TIMEOUT` - HTTP timeout for LLM API calls in seconds (default: `60`)
- `LLM_TEMPERATURE` - LLM creativity parameter, 0.0-1.0 (default: `0.2`)

### Content Processing
- `ANCHOR_SANITIZE` - Enable anchor text sanitization (`0` or `1`)
- `ANCHOR_REQUIRE_KEYWORDS` - Require keywords in anchor text (`0` or `1`)
- `PROMPT_MODE` - How to send article content: `paragraphs`, `full`, or `both` (default: `both`)

### QA Configuration
- `QA_MODE` - QA verification mode: `auto`, `ai`, or `fallback` (default: `auto`)
- `QA_THRESHOLD` - Minimum QA rating for acceptance, 0-10 (default: `7`)

### Pipeline Configuration
- `RETRY_MAX_ATTEMPTS` - Maximum selection retry attempts (default: `3`)
- `USE_CREWAI_AGENTS` - Enable CrewAI agent orchestration (`0` or `1`)

### Flow Persistence (Redis)
- `USE_FLOW` - Enable CrewAI flow state persistence (`0` or `1`)
- `FLOW_REDIS_URL` - Redis URL for flow persistence (default: `redis://localhost:6379/2`)

### Celery (FastAPI Async Processing)
- `CELERY_BROKER_URL` - Redis broker URL for Celery (default: `redis://localhost:6379/0`)
- `CELERY_RESULT_BACKEND` - Redis backend URL for Celery results (default: `redis://localhost:6379/1`)

## *Full workflow guide* - Click Here 👉 ["docs/Project_Complete_Workflow_Technical_Guide/Workflow_Technical_Guide.md"](docs/Project_Complete_Workflow_Technical_Guide/Workflow_Technical_Guide.md)
