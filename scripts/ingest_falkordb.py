#!/usr/bin/env python3
"""Load the generated NovaTech dataset into FalkorDB as an Entity property graph."""
from __future__ import annotations

import argparse
import csv
from configparser import ConfigParser
import json
import os
import re
from collections import defaultdict
from pathlib import Path

LABELS = {
    "employees": "Employee", "teams": "Team", "projects": "Project",
    "tasks": "Task", "decisions": "Decision", "meetings": "Meeting",
    "documents": "Document", "expertise": "Expertise",
}
RELATIONSHIPS = {
    "EMPLOYEE_BELONGS_TO_TEAM", "EMPLOYEE_OWNS_PROJECT", "EMPLOYEE_ASSIGNED_TO_TASK",
    "PROJECT_HAS_TASK", "PROJECT_DEPENDS_ON_PROJECT", "TASK_BLOCKED_BY_TASK",
    "MEETING_MADE_DECISION", "DECISION_AFFECTS_PROJECT", "DECISION_MADE_BY_EMPLOYEE",
    "DOCUMENT_MENTIONS_PROJECT", "EMPLOYEE_HAS_EXPERTISE", "PROJECT_BLOCKED_BY_DECISION",
}

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def markdown_fields(path: Path, kind: str) -> dict:
    text = path.read_text(encoding="utf-8")
    def field(label: str, default=""):
        match = re.search(rf"^- {re.escape(label)}: (.*)$", text, re.M)
        return match.group(1).strip() if match else default
    title_match = re.search(r"^# (.+)$", text, re.M)
    props = {"title": title_match.group(1) if title_match else path.stem, "text": text, "source_path": str(path)}
    if kind == "meeting":
        props.update({"date": field("Date"), "status": field("Status", "final"),
                      "attendee_ids": [x.strip() for x in field("Attendees").split(",") if x.strip()],
                      "source_id": f"MEETING-{field('Meeting ID')}"})
        props["decision_ids"] = re.findall(r"^## Decision (DEC\d+):", text, re.M)
        props["id"] = field("Meeting ID")
    else:
        props.update({"source_id": field("Source ID"), "status": field("Status"), "updated_at": field("Updated")})
        props["id"] = field("Document ID")
    return props

def property_values(value):
    """FalkorDB node properties are scalar or flat arrays; encode nested JSON values."""
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, list) and any(isinstance(x, (dict, list)) for x in value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return value

def load_records(data_dir: Path):
    records = defaultdict(list)
    with (data_dir / "employees.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["expertise"] = [x.strip() for x in row["expertise"].split(";") if x.strip()]
            records["employees"].append(row)
    for kind in ("teams", "projects", "tasks", "decisions"):
        records[kind].extend(read_json(data_dir / f"{kind}.json"))
    manifest = read_json(data_dir / "manifest.json")
    records["expertise"].extend(manifest.get("expertise_nodes", []))
    for path in sorted((data_dir / "meetings").glob("meeting_*.md")):
        records["meetings"].append(markdown_fields(path, "meeting"))
    for path in sorted((data_dir / "documents").glob("policy_*.md")):
        records["documents"].append(markdown_fields(path, "document"))
    relationships = read_json(data_dir / "relationships.json")
    document_projects = defaultdict(list)
    for edge in relationships:
        if edge.get("type") == "DOCUMENT_MENTIONS_PROJECT":
            document_projects[edge["source_id"]].append(edge["target_id"])
    for doc in records["documents"]:
        doc["mentioned_project_ids"] = document_projects[doc["id"]]
    return records, relationships

def main():
    config = ConfigParser()
    config_path = Path(__file__).resolve().parents[1] / "atlas_search_copilot" / "cloud_config.ini"
    if config_path.exists():
        config.read(config_path, encoding="utf-8")
    connection = config["falkordb"] if config.has_section("falkordb") else {}
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    ap.add_argument("--host", default=os.environ.get("FALKORDB_HOST", connection.get("host", "localhost")))
    ap.add_argument("--port", type=int, default=int(os.environ.get("FALKORDB_PORT", connection.get("port", "6379"))))
    ap.add_argument("--password", default=os.environ.get("FALKORDB_PASSWORD", connection.get("password")))
    ap.add_argument("--username", default=os.environ.get("FALKORDB_USERNAME", connection.get("username")))
    ssl_default = os.environ.get("FALKORDB_SSL", connection.get("ssl", "false")).lower() in {"1", "true", "yes"}
    ap.add_argument("--ssl", action="store_true", default=ssl_default)
    ap.add_argument("--graph", default=os.environ.get("FALKORDB_GRAPH", connection.get("graph", "novatech")), help="Graph name (default: novatech).")
    ap.add_argument("--batch-size", type=int, default=100)
    args = ap.parse_args()
    if args.batch_size < 1:
        ap.error("--batch-size must be a positive integer")
    if args.host != "localhost" and not args.password:
        ap.error("Cloud requires a password; set it in atlas_search_copilot/cloud_config.ini or FALKORDB_PASSWORD.")
    data_dir = args.data_dir.resolve()
    records, relationships = load_records(data_dir)
    ids = {r["id"] for group in records.values() for r in group if r.get("id")}
    for kind, group in records.items():
        for record in group:
            if not record.get("id"):
                raise ValueError(f"A {kind} record is missing its ID")
    for edge in relationships:
        if edge.get("type") not in RELATIONSHIPS:
            raise ValueError(f"Unknown relationship type: {edge.get('type')}")
        for endpoint in ("source_id", "target_id"):
            if edge.get(endpoint) not in ids:
                raise ValueError(f"{edge.get('type')} has unresolved {endpoint}: {edge.get(endpoint)}")

    try:
        from falkordb import FalkorDB
    except ImportError as exc:
        raise SystemExit("FalkorDB client missing. Install it with: python -m pip install FalkorDB") from exc
    db = FalkorDB(host=args.host, port=args.port, password=args.password,
                  username=args.username, ssl=args.ssl)
    graph = db.select_graph(args.graph)
    total_nodes = 0
    for kind, label in LABELS.items():
        group = records[kind]
        query = f"UNWIND $rows AS row MERGE (n:Entity {{id: row.id}}) SET n:{label} SET n += row.properties"
        for start in range(0, len(group), args.batch_size):
            batch = group[start:start + args.batch_size]
            rows = [{"id": r["id"], "properties": {k: property_values(v) for k, v in r.items()}}
                    for r in batch]
            graph.query(query, {"rows": rows})
            total_nodes += len(batch)

    grouped = defaultdict(list)
    for edge in relationships:
        props = {k: property_values(v) for k, v in edge.items() if k not in {"type", "source_id", "target_id"}}
        grouped[edge["type"]].append({"source_id": edge["source_id"], "target_id": edge["target_id"], "properties": props})
    total_edges = 0
    for rel_type, group in grouped.items():
        # Relationship identifiers come only from the allowlist above; values stay parameterized.
        query = (f"UNWIND $rows AS row MATCH (a:Entity {{id: row.source_id}}), "
                 f"(b:Entity {{id: row.target_id}}) MERGE (a)-[r:{rel_type}]->(b) SET r += row.properties")
        for start in range(0, len(group), args.batch_size):
            batch = group[start:start + args.batch_size]
            graph.query(query, {"rows": batch})
            total_edges += len(batch)
    result = graph.query("MATCH (n:Entity) RETURN count(n)").result_set
    print(f"Loaded {total_nodes} nodes and {total_edges} relationships into graph '{args.graph}'.")
    print(f"FalkorDB reports {result[0][0]} Entity nodes in that graph.")

if __name__ == "__main__":
    main()
