# NovaTech Company Brain — Atlas Search slice

The first Streamlit slice follows Atlas Search's blocking decision in FalkorDB and displays the decision owner, meeting, dependent projects, tasks, and linked documents. The live query and its saved result belong to this folder.

## Connect to FalkorDB Cloud

Copy `cloud_config.example.ini` to `cloud_config.ini` and enter the FalkorDB Cloud connection details from your account. The real config file is ignored by Git; do not commit it or paste the password into chat.

```ini
[falkordb]
host = your-cloud-endpoint
port = 6379
username = default
password = your-cloud-password
ssl = true
graph = novatech
```

Use the host, port, username, TLS setting, and password shown in your Cloud connection details. Keep credentials private and do not commit them.

## Import the existing dataset

From the repository root, install the app's Python dependencies and run the existing importer against the configured cloud endpoint:

```powershell
.\.venv\Scripts\python.exe -m pip install -r atlas_search_copilot\requirements.txt
.\.venv\Scripts\python.exe scripts\ingest_falkordb.py --graph novatech
```

FalkorDB Browser is available from the Cloud console for the selected database. In its query editor, run this small inspection query:

```cypher
MATCH (p:Project {id: 'PRJ001'})-[:PROJECT_BLOCKED_BY_DECISION]->(d:Decision)
RETURN p.name, p.status, p.blockers, d.id, d.title, d.description, d.status
```

The app's full parameterized Cypher query is `queries/atlas_search.cypher`.

## Save the live query result and start Streamlit

```powershell
.\.venv\Scripts\python.exe atlas_search_copilot\graph_query.py
.\.venv\Scripts\python.exe -m streamlit run atlas_search_copilot\app.py
```

The query script writes `results/atlas_search_result.json`; clicking the app button refreshes and saves the same result. Environment variables (`FALKORDB_HOST`, `FALKORDB_PORT`, `FALKORDB_USERNAME`, `FALKORDB_PASSWORD`, `FALKORDB_SSL`, `FALKORDB_GRAPH`) override the local config file.

## Company Brain agent

The app accepts natural-language questions and queries the live FalkorDB graph. It follows linked project, decision, people, task, expertise, and document records. Answers cite graph record IDs and put current documents ahead of draft or superseded guidance. When Gemini is configured, it chooses the graph lookups and can chain multiple read-only tools before answering.

The included challenge investigations are available from the **Try a challenge investigation** selector. Example free-form questions:

- `Why is Atlas Search delayed, who made the decision, and what depends on it?`
- `Which upstream identity event blocks Drift Data Mesh, and who can resolve it?`
- `Who knows data lineage?`
- `Which current policy supersedes the older Halo Audit guidance?`

Run against local Docker FalkorDB by setting `FALKORDB_HOST=localhost`, `FALKORDB_PORT=6379`, and `FALKORDB_GRAPH=novatech`, then start Streamlit with:

```powershell
.\.venv\Scripts\python.exe -m streamlit run atlas_search_copilot\app.py
```

The visible **Graph evidence and agent trace** panel shows the selected tools, relationship path, and record IDs used to construct each answer. Follow-up questions that refer to “it” or “this project” reuse the last project in the current browser session; **Start a new conversation** resets that context.

## Gemini tool-calling agent

When a Gemini API key is configured, Gemini now selects and calls read-only graph tools, can chain multiple lookups, then synthesizes a cited answer from the results. Python owns and validates every tool implementation; the model cannot send Cypher or modify graph data. Tool names and parameters are declared in `agent.py`, while the bounded call loop and citation checks are in `llm.py`. The agent has a six-round and ten-call limit and falls back to the deterministic agent if Gemini is unavailable or its citations do not match returned record IDs.

Available tools:

- `list_projects` — find projects by name or status words.
- `get_project_dossier` — fetch a project's decisions, owners, meetings, tasks, dependencies, and linked documents.
- `find_expertise` — find employees and teams by expertise.
- `search_documents` — search document text and optionally filter by project.
- `search_tasks` — search tasks and optionally filter by project.
- `get_person_profile` — fetch an employee's team, expertise, owned projects, and assigned tasks.

The API key is read from `atlas_search_copilot/.env` (or the process environment); the local file is ignored by Git. The model defaults to `gemini-3.8-flash`; override it with `GOOGLE_GENAI_MODEL` if needed.

## Agent logging and evaluation

Each completed turn is appended to `atlas_search_copilot/logs/agent_events.jsonl`, with rotation and four retained backups. Events capture latency, selected tools and arguments, record counts, source IDs, citations, validation status, and fallback/error state. Raw FalkorDB tool result payloads are not copied to the log. Question and answer text are logged locally by default to support manual evaluation; set `COMPANY_BRAIN_LOG_CONTENT=false` in `.env` for metadata-only logging. The log directory is ignored by Git. Users can rate answers with thumbs up/down; the sidebar's **Evaluation & logs** panel summarizes model/fallback counts, latency, tool usage, citation checks, errors, and feedback.

Add your key to `atlas_search_copilot/.env`:

```powershell
GEMINI_API_KEY=your-key
GOOGLE_GENAI_MODEL=gemini-3.8-flash
```

Install the updated requirements and restart the app so the running process loads the key:

```powershell
.\.venv\Scripts\python.exe -m pip install -r atlas_search_copilot\requirements.txt
.\.venv\Scripts\python.exe -m streamlit run atlas_search_copilot\app.py
```
