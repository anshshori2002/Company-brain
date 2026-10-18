"""Retrieve the Atlas Search blocker evidence from FalkorDB Cloud or local FalkorDB."""
from __future__ import annotations

import argparse
from configparser import ConfigParser
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from falkordb import FalkorDB

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
QUERY_PATH = ROOT / "queries" / "atlas_search.cypher"
RESULT_PATH = ROOT / "results" / "atlas_search_result.json"
CONFIG_PATH = ROOT / "cloud_config.ini"


def _connection_settings() -> dict[str, Any]:
    config = ConfigParser()
    if CONFIG_PATH.exists():
        config.read(CONFIG_PATH, encoding="utf-8")
    section = config["falkordb"] if config.has_section("falkordb") else {}
    host = os.getenv("FALKORDB_HOST", section.get("host", ""))
    is_local = host.lower() in {"localhost", "127.0.0.1", "::1"}
    return {
        "host": host,
        "port": int(os.getenv("FALKORDB_PORT", section.get("port", "6379"))),
        # Local Docker FalkorDB is unauthenticated by default. Never inherit
        # Cloud credentials when the host is local, even if they exist in the
        # process environment.
        "username": None if is_local else (os.getenv("FALKORDB_USERNAME", section.get("username", "default")) or None),
        "password": None if is_local else (os.getenv("FALKORDB_PASSWORD", section.get("password", "")) or None),
        "ssl": os.getenv("FALKORDB_SSL", "false" if is_local else section.get("ssl", "false")).lower() in {"1", "true", "yes"},
        "graph": os.getenv("FALKORDB_GRAPH", section.get("graph", "novatech")),
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items() if item is not None}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value if item is not None]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def fetch_atlas_search(project_id: str = "PRJ001") -> dict[str, Any]:
    """Execute the checked-in, parameterized Cypher query and return its first row."""
    settings = _connection_settings()
    if not settings["host"] or "paste-cloud" in settings["host"].lower():
        raise RuntimeError("Add your Cloud endpoint to atlas_search_copilot/cloud_config.ini first.")
    if not settings["password"] and settings["host"].lower() not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Add the Cloud password to the ignored cloud_config.ini file first.")
    client = FalkorDB(
        **{key: settings[key] for key in ("host", "port", "password", "username", "ssl")},
        socket_connect_timeout=5,
        socket_timeout=30,
    )
    graph = client.select_graph(settings["graph"])
    result = graph.query(QUERY_PATH.read_text(encoding="utf-8"), {"project_id": project_id})
    if not result.result_set:
        raise LookupError(f"No blocker decision found for project {project_id}.")
    columns = []
    for header in result.header:
        if isinstance(header, (list, tuple)):
            # FalkorDB client headers are commonly shaped like [type, name].
            # Prefer the actual textual column name rather than the numeric type tag.
            name = next(
                (item for item in header if isinstance(item, (str, bytes))),
                header[-1] if header else "",
            )
        else:
            name = header
        columns.append(name.decode() if isinstance(name, bytes) else str(name))
    record = {column: _json_value(value) for column, value in zip(columns, result.result_set[0])}
    record["query_file"] = str(QUERY_PATH.relative_to(ROOT))
    record["executed_at_utc"] = datetime.now(timezone.utc).isoformat()
    return record


def save_result(record: dict[str, Any], path: Path = RESULT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", default="PRJ001")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()
    record = fetch_atlas_search(args.project_id)
    if not args.no_save:
        print(f"Saved result: {save_result(record)}")
    print(json.dumps(record, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
