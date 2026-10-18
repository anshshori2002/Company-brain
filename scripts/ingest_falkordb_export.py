#!/usr/bin/env python3
"""Import a typed-node/edge CSV export into FalkorDB.

By default this validates the export and reports counts without changing the graph.
Pass --replace only after confirming that the target graph may be cleared.
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import os
from collections import defaultdict
from pathlib import Path
import re
from typing import Any

NODE_LABELS = (
    "Decision", "Document", "Employee", "Expertise", "Meeting", "Project", "Task", "Team",
)
RELATIONSHIPS = {
    "DECISION_AFFECTS_PROJECT", "DECISION_MADE_BY_EMPLOYEE", "DOCUMENT_MENTIONS_PROJECT",
    "EMPLOYEE_ASSIGNED_TO_TASK", "EMPLOYEE_BELONGS_TO_TEAM", "EMPLOYEE_HAS_EXPERTISE",
    "EMPLOYEE_OWNS_PROJECT", "MEETING_MADE_DECISION", "PROJECT_BLOCKED_BY_DECISION",
    "PROJECT_DEPENDS_ON_PROJECT", "PROJECT_HAS_TASK", "TASK_BLOCKED_BY_TASK",
}


def parse_export_value(value: str) -> Any:
    """Decode arrays/maps where possible while preserving ordinary CSV strings."""
    if not value:
        return ""
    if value[:1] in "[{":
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(value)
            except (SyntaxError, ValueError):
                return value
            if isinstance(parsed, (list, dict)):
                return parsed
    return value


def property_value(value: Any) -> Any:
    """Encode nested values as JSON; FalkorDB only accepts flat primitive arrays."""
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, (list, tuple)) and any(isinstance(item, (dict, list, tuple)) for item in value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [
            {key: parse_export_value(value) for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def load_export(data_dir: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    nodes: dict[str, list[dict[str, Any]]] = {}
    all_ids: set[str] = set()
    for label in NODE_LABELS:
        path = data_dir / f"nodes_{label}.csv"
        if not path.is_file():
            raise FileNotFoundError(f"Required typed node file is missing: {path}")
        rows = read_csv(path)
        seen: set[str] = set()
        for row in rows:
            node_id = str(row.get("id", ""))
            if not node_id:
                raise ValueError(f"A row in {path.name} is missing id")
            if node_id in seen:
                raise ValueError(f"Duplicate node id {node_id} in {path.name}")
            if node_id in all_ids:
                raise ValueError(f"Node id {node_id} appears in more than one typed node file")
            seen.add(node_id)
            all_ids.add(node_id)
        nodes[label] = rows

    relationships: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(data_dir.glob("edges_*.csv")):
        rel_type = path.stem.removeprefix("edges_")
        if rel_type not in RELATIONSHIPS or not re.fullmatch(r"[A-Z][A-Z0-9_]*", rel_type):
            raise ValueError(f"Unrecognized relationship type in {path.name}")
        for row in read_csv(path):
            source_id, target_id = str(row.get("from_id", "")), str(row.get("to_id", ""))
            if source_id not in all_ids or target_id not in all_ids:
                raise ValueError(f"Unresolved endpoint in {path.name}: {source_id} -> {target_id}")
            relationships[rel_type].append(row)
    if not relationships:
        raise ValueError(f"No edges_*.csv files found in {data_dir}")
    return nodes, dict(relationships)


def main() -> None:
    default_dir = Path(__file__).resolve().parents[1] / "falkordb-export-novatech-expanded"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=default_dir)
    parser.add_argument("--host", default=os.getenv("FALKORDB_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("FALKORDB_PORT", "6379")))
    parser.add_argument("--username", default=os.getenv("FALKORDB_USERNAME") or None)
    parser.add_argument("--password", default=os.getenv("FALKORDB_PASSWORD") or None)
    parser.add_argument("--ssl", action="store_true", default=os.getenv("FALKORDB_SSL", "false").lower() in {"1", "true", "yes"})
    parser.add_argument("--graph", default=os.getenv("FALKORDB_GRAPH", "novatech"))
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--replace", action="store_true", help="Clear all existing graph records before import.")
    parser.add_argument("--dry-run", action="store_true", help="Validate source files and report counts only.")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")

    data_dir = args.data_dir.resolve()
    nodes, relationships = load_export(data_dir)
    node_count = sum(map(len, nodes.values()))
    edge_count = sum(map(len, relationships.values()))
    print(f"Validated {node_count} typed nodes and {edge_count} relationships from {data_dir}.")
    if args.dry_run:
        return

    try:
        from falkordb import FalkorDB
    except ImportError as exc:
        raise SystemExit("FalkorDB client missing. Install it with: python -m pip install FalkorDB") from exc

    db = FalkorDB(host=args.host, port=args.port, password=args.password,
                  username=args.username, ssl=args.ssl)
    graph = db.select_graph(args.graph)
    existing_nodes = graph.query("MATCH (n) RETURN count(n)").result_set[0][0]
    existing_edges = graph.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
    if (existing_nodes or existing_edges) and not args.replace:
        raise SystemExit(
            f"Graph '{args.graph}' already contains {existing_nodes} nodes and {existing_edges} relationships. "
            "Use --replace only when you intend to delete its existing contents."
        )
    if args.replace:
        graph.query("MATCH (n) DETACH DELETE n")

    for label, rows in nodes.items():
        query = f"UNWIND $rows AS row MERGE (n:Entity {{id: row.id}}) SET n:{label} SET n += row.properties"
        for start in range(0, len(rows), args.batch_size):
            batch = rows[start:start + args.batch_size]
            payload = [
                {"id": row["id"], "properties": {key: property_value(value) for key, value in row.items()}}
                for row in batch
            ]
            graph.query(query, {"rows": payload})

    for rel_type, rows in relationships.items():
        query = (
            "UNWIND $rows AS row MATCH (a:Entity {id: row.from_id}), (b:Entity {id: row.to_id}) "
            f"MERGE (a)-[r:{rel_type} {{id: row.id}}]->(b) SET r += row.properties"
        )
        for start in range(0, len(rows), args.batch_size):
            batch = rows[start:start + args.batch_size]
            payload = [
                {"id": str(row["id"]), "from_id": str(row["from_id"]), "to_id": str(row["to_id"]),
                 "properties": {key: property_value(value) for key, value in row.items()
                                if key not in {"from_id", "to_id"}}}
                for row in batch
            ]
            graph.query(query, {"rows": payload})

    final_nodes = graph.query("MATCH (n:Entity) RETURN count(n)").result_set[0][0]
    final_edges = graph.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
    print(f"Imported {node_count} typed nodes and {edge_count} relationships into '{args.graph}'.")
    print(f"FalkorDB reports {final_nodes} Entity nodes and {final_edges} relationships.")


if __name__ == "__main__":
    main()
