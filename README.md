# NovaTech Synthetic Company Knowledge Dataset

This repository contains a deterministic, fictional company history designed to demonstrate evidence tracing and multi-hop reasoning in a graph database. NovaTech, every employee, and every company record are invented. The generator produces structured JSON, employee CSV, and Markdown source documents without connecting to FalkorDB.

## Generate the dataset

From the repository root, run:

    python scripts/generate_data.py
    python scripts/validate_data.py

By default, the generator writes to data/ with seed 20251016. It recreates the named generated files while leaving unrelated files in the output directory alone. To choose a different output directory or seed:

    python scripts/generate_data.py --output-dir .\sample-data --seed 42

Counts can be changed independently:

    python scripts/generate_data.py --employees 24 --teams 5 --projects 12 --meetings 36 --decisions 34 --tasks 60 --documents 18
    python scripts/validate_data.py --data-dir .\data

The five designed investigation scenarios require minimum counts of 5 employees, 5 teams, 5 projects, 8 meetings, 8 decisions, 30 tasks, and 9 documents. The validator compares generated counts with manifest.json and warns when they differ from the default targets.

## Files and entities

- employees.csv: employee ID, fictional name, title, team, expertise, and timestamps.
- teams.json: teams and short descriptions.
- projects.json: project owner and team, current status plus dated status history, deadline, blockers, risks, and timestamps.
- tasks.json: project tasks, assignees, status, due dates, and task blocker IDs.
- decisions.json: decision text and status, meeting, decision maker, affected projects, and timestamps.
- meetings/meeting_NNN.md: meeting date, attendees, decision rationale, and recorded decision status.
- documents/policy_NNN.md: internal fictional policy and technical notes. Documents have source IDs, status, and update time. Current, draft, and superseded records help resolve historical conflicts.
- relationships.json: graph edges, with source_id and target_id referencing IDs in the entity files or expertise nodes.
- scenarios.json: investigation questions and the evidence IDs needed to answer them.
- manifest.json: seed, record counts, relationship types, status values, expertise node catalog, and schema version.

Relationship types:

| Type | Meaning |
| --- | --- |
| EMPLOYEE_BELONGS_TO_TEAM | Employee is a member of a team |
| EMPLOYEE_OWNS_PROJECT | Employee owns a project |
| EMPLOYEE_ASSIGNED_TO_TASK | Employee is assigned to a task |
| PROJECT_HAS_TASK | Task belongs to a project |
| PROJECT_DEPENDS_ON_PROJECT | Project relies on another project's output |
| TASK_BLOCKED_BY_TASK | Task cannot proceed until its blocker is finished |
| MEETING_MADE_DECISION | Meeting records a decision |
| DECISION_AFFECTS_PROJECT | Decision changes or governs a project |
| DECISION_MADE_BY_EMPLOYEE | Employee made a decision |
| DOCUMENT_MENTIONS_PROJECT | Document contains evidence relevant to a project |
| EMPLOYEE_HAS_EXPERTISE | Employee has a named expertise node |
| PROJECT_BLOCKED_BY_DECISION | Project progress is gated by a decision |

IDs are stable within the generated dataset (EMP001, PRJ001, TASK001, DEC001, and so on). Timestamps use UTC ISO 8601 values. The fixed seed makes generated records and supplemental content reproducible.

## Designed investigation questions

The scenarios are stored in scenarios.json; each lists evidence IDs and a suggested relationship path.

1. **Atlas Search:** Why is it delayed, which decision caused the blocker, who made it, and which other projects are affected? Trace PRJ001 through its blocked tasks to DEC001, the meeting MTG001, the decision maker's expertise, and the affected projects. Read the isolation standard alongside the superseded pilot checklist.
2. **Cinder Identity:** What recovery control is missing, and how does the issue reach Drift Data Mesh and Halo Audit? Use DEC003, MTG003, the recovery runbook, and the project/task dependency links.
3. **Drift Data Mesh:** Which identity event prevents lineage export, who can help, and why? Join DEC004 and MTG004 to the event contract and lineage interface documents; follow the task and project dependencies to Halo Audit.
4. **Echo Console:** Why is the project at risk, what security decision controls its status display, and who owns relevant expertise? Compare the current security posture API guide with the draft release notes and follow DEC005 back to its meeting.
5. **Halo Audit:** Why is the export at risk, which dependency is upstream, and what policy supersedes older guidance? Trace the Drift dependency and compare the current 180-day retention policy with superseded export notes.

These are multi-hop questions: an answer should cite the project state, task or project blocker, decision, meeting rationale, and relevant owner or document, rather than infer from one isolated record.

## Validation

scripts/validate_data.py checks required fields, unique IDs, timestamps, allowed statuses, manifest counts, embedded references, every relationship endpoint, required relationship types, graph reachability, and evidence completeness for each investigation scenario. It prints a readable summary and exits non-zero on critical failures.

## Load into FalkorDB

Generation and ingestion are separate scripts. Start a local FalkorDB instance with Docker:

    docker run -d --name falkordb -p 6379:6379 -p 3000:3000 -v falkordb_data:/var/lib/falkordb/data falkordb/falkordb

Install the official Python client and run the importer:

    python -m pip install FalkorDB
    python scripts/ingest_falkordb.py --graph novatech

The importer reads the generated JSON, CSV, and Markdown, then upserts typed nodes and edges into the named graph. Markdown contents are stored on Meeting and Document nodes, preserving their source IDs and status metadata. It checks relationship endpoints before connecting to the database and prints the loaded node and edge counts. You can open the FalkorDB browser at http://localhost:3000.

The importer defaults to localhost:6379 and graph name novatech. Use --host, --port, --graph, --data-dir, or --batch-size to change those settings. For a password-protected server, set FALKORDB_PASSWORD in your environment. Re-running the importer is safe for matching IDs and relationships; it upserts records and does not delete existing graph data.

For example, after loading, query a project and its blocking decisions with:

    MATCH (p:Project {id: 'PRJ001'})-[:PROJECT_BLOCKED_BY_DECISION]->(d:Decision)
    RETURN p.name, p.status, d.id, d.title, d.status

The scenario catalog powers the multi-hop demo questions in the NovaTech Company Brain agent. The Streamlit app routes natural-language questions to parameterized FalkorDB tools, follows graph relationships across projects, decisions, people, tasks, dependencies, and documents, and shows the evidence path and source IDs. See [atlas_search_copilot/README.md](atlas_search_copilot/README.md) for setup and usage.

To load a typed-node/edge CSV export such as `falkordb-export-novatech-expanded`, use `scripts/ingest_falkordb_export.py`. It validates the export first; pass `--replace` only when you intend to clear the target graph before importing.
