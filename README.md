# Company Brain

Company Brain is a Streamlit application that lets users ask natural-language questions about company projects, tasks, teams, employees, decisions, and dependencies. It uses a local Ollama model to translate questions into OpenCypher, queries a FalkorDB graph, and turns the results into a short operational summary.

## Features

- Natural-language chat interface built with Streamlit.
- Local `llama3.2` Ollama model for:
  - Natural language to OpenCypher translation.
  - Plain-English summaries of graph results.
- FalkorDB Cloud connection loaded securely from a `.env` file.
- Recommended operational query in the sidebar.
- Schema exploration utilities for inspecting labels, properties, and relationships.
- Conversation history maintained during the Streamlit session.

## Architecture

1. A user submits a question in the Streamlit interface.
2. Ollama converts the question into a single OpenCypher query using the graph schema in `app.py`.
3. The generated query runs against the `novatech` graph in FalkorDB.
4. The matching records are displayed and passed back to Ollama for a concise explanation.

## Prerequisites

- Python 3.9 or newer.
- A FalkorDB Cloud instance containing the `novatech` graph.
- [Ollama](https://ollama.com/) installed and running locally.
- The `llama3.2` model downloaded in Ollama.

Pull the model before starting the application:

```bash
ollama pull llama3.2
```

## Installation

Clone or download this repository, then create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install the Python dependencies:

```bash
pip install -r requirement.txt
```

The application also imports the Ollama Python client. If it is not already installed in your environment, install it with:

```bash
pip install ollama
```

## Configuration

Create a `.env` file in the project root. Do not commit this file or share its contents:

```env
FALKORDB_HOST="your-falkordb-host"
FALKORDB_PORT=57900
FALKORDB_USER="your-falkordb-user"
FALKORDB_PASSWORD="your-falkordb-password"
```

The application connects to the graph named `novatech`. Make sure the graph exists and that the configured FalkorDB user has permission to query it.

## Running the application

Start Ollama if it is not already running, then launch Streamlit:

```bash
streamlit run app.py
```

Streamlit will print a local URL, normally:

```text
http://localhost:8501
```

Open that URL in a browser and ask questions such as:

- `Who has Infrastructure expertise and which team do they belong to?`
- `What projects depend on Platform Expansion?`
- `Which decisions affected a project?`
- `Show me a database summary.`

## Utility scripts

### Test the FalkorDB connection

```bash
python connect.py
```

This loads the `.env` configuration, connects to FalkorDB, selects the `novatech` graph, and reports whether the connection succeeds.

### Explore the graph schema and sample data

```bash
python explore_data.py
```

This reports:

- Unique node labels and their counts.
- Sample node properties.
- A sample of relationship paths.

## Graph schema

The application currently generates queries for these node labels:

`Team`, `Task`, `Project`, `Meeting`, `Expertise`, `Entity`, `Employee`, `Document`, and `Decision`.

Known relationship types include:

| Source | Relationship | Target |
| --- | --- | --- |
| `Employee` | `EMPLOYEE_HAS_EXPERTISE` | `Expertise` |
| `Project` | `PROJECT_HAS_TASK` | `Task` |
| `Employee` | `EMPLOYEE_ASSIGNED_TO_TASK` | `Task` |
| `Decision` | `DECISION_AFFECTS_PROJECT` | `Project` |
| `Decision` | `DECISION_MADE_BY_EMPLOYEE` | `Employee` |
| `Meeting` | `MEETING_MADE_DECISION` | `Decision` |
| `Document` | `DOCUMENT_MENTIONS_PROJECT` | `Project` |
| `Employee` | `EMPLOYEE_BELONGS_TO_TEAM` | `Team` |
| `Task` | `TASK_BLOCKED_BY_TASK` | `Task` |
| `Employee` | `EMPLOYEE_OWNS_PROJECT` | `Project` |
| `Decision` | `PROJECT_BLOCKED_BY_DECISION` | `Project` |
| `Project` | `PROJECT_DEPENDS_ON_PROJECT` | `Project` |

Labels and relationship names are case-sensitive. If the data model changes, update the schema context and examples in `app.py` so Ollama generates compatible queries.

## Troubleshooting

### FalkorDB connection failure

- Confirm that `.env` is in the project root.
- Check that all `FALKORDB_*` values are present and valid.
- Confirm that the FalkorDB instance is reachable from your network.
- Verify that the `novatech` graph exists.

### Ollama connection or model errors

- Confirm that Ollama is installed and running.
- Run `ollama list` to verify that `llama3.2` is available.
- Run `ollama pull llama3.2` if the model is missing.
- Confirm that the `ollama` Python package is installed in the active virtual environment.

### No matching results

The generated query is limited to five returned records and depends on the schema defined in `app.py`. Use the graph exploration script to confirm the actual labels, properties, and relationship names in FalkorDB.

## Security notes

- Keep `.env` out of version control. It is already excluded by `.gitignore`.
- Never paste FalkorDB credentials into source files, issues, logs, or screenshots.
- Treat generated OpenCypher as database input and review generated queries when troubleshooting unexpected results.
- Use a least-privilege FalkorDB account for the application.

## Project files

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit UI, Ollama integration, OpenCypher generation, and graph querying |
| `connect.py` | Basic FalkorDB connection check |
| `explore_data.py` | Graph labels, sample properties, and relationship inspection |
| `requirement.txt` | Core Python dependencies |
| `.env` | Local FalkorDB configuration; do not commit |
