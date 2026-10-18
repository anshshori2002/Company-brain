"""Evidence-grounded company knowledge agent backed by FalkorDB traversals."""
from __future__ import annotations

import os
import re
from typing import Any

from falkordb import FalkorDB

from graph_query import _connection_settings, _json_value
from llm import run_tool_calling_agent, run_web_search_agent


def _column_name(header: Any) -> str:
    if isinstance(header, (list, tuple)):
        header = next((value for value in header if isinstance(value, (str, bytes))), header[-1] if header else "")
    return header.decode() if isinstance(header, bytes) else str(header)


def _rows(result: Any) -> list[dict[str, Any]]:
    columns = [_column_name(header) for header in result.header]
    return [
        {column: _json_value(value) for column, value in zip(columns, row)}
        for row in result.result_set
    ]


def _clean(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


_GRAPH_NODE_SCHEMA = {
    "Project": {"description": "Company initiatives and workstreams.", "key_properties": ["id", "name", "status", "description", "blockers", "deadline", "risks"]},
    "Decision": {"description": "Decisions that affect or block projects, with a title, rationale, and status.", "key_properties": ["id", "title", "description", "status"]},
    "Employee": {"description": "People who own projects, make decisions, or are assigned tasks.", "key_properties": ["id", "name", "title"]},
    "Meeting": {"description": "Meeting records that can provide the source for a decision.", "key_properties": ["id", "title", "date", "text"]},
    "Task": {"description": "Project work items, their status and priority, and task dependencies.", "key_properties": ["id", "title", "status", "priority"]},
    "Document": {"description": "Source documents linked to projects, with text and lifecycle metadata.", "key_properties": ["id", "title", "status", "updated_at", "source_id", "text"]},
    "Expertise": {"description": "Skills associated with employees.", "key_properties": ["id", "name"]},
    "Team": {"description": "Organizational teams associated with employees.", "key_properties": ["id", "name"]},
}

_GRAPH_RELATIONSHIP_SCHEMA = {
    "PROJECT_BLOCKED_BY_DECISION": {"from": "Project", "to": "Decision", "meaning": "The project is blocked by this decision."},
    "DECISION_AFFECTS_PROJECT": {"from": "Decision", "to": "Project", "meaning": "The decision affects this project."},
    "DECISION_MADE_BY_EMPLOYEE": {"from": "Decision", "to": "Employee", "meaning": "The employee made or owns the decision."},
    "MEETING_MADE_DECISION": {"from": "Meeting", "to": "Decision", "meaning": "The meeting record documents the decision."},
    "PROJECT_HAS_TASK": {"from": "Project", "to": "Task", "meaning": "The task belongs to the project."},
    "EMPLOYEE_ASSIGNED_TO_TASK": {"from": "Employee", "to": "Task", "meaning": "The employee is assigned to the task."},
    "TASK_BLOCKED_BY_TASK": {"from": "Task", "to": "Task", "meaning": "The task is blocked by another task."},
    "PROJECT_DEPENDS_ON_PROJECT": {"from": "Project", "to": "Project", "meaning": "The first project depends on the second project."},
    "DOCUMENT_MENTIONS_PROJECT": {"from": "Document", "to": "Project", "meaning": "The source document mentions the project."},
    "EMPLOYEE_OWNS_PROJECT": {"from": "Employee", "to": "Project", "meaning": "The employee owns the project."},
    "EMPLOYEE_HAS_EXPERTISE": {"from": "Employee", "to": "Expertise", "meaning": "The employee has this expertise."},
    "EMPLOYEE_BELONGS_TO_TEAM": {"from": "Employee", "to": "Team", "meaning": "The employee belongs to this team."},
}


class CompanyBrainAgent:
    """Company knowledge agent with Gemini-selected, read-only graph tools."""

    def __init__(self) -> None:
        settings = _connection_settings()
        if not settings["host"] or "paste-cloud" in settings["host"].lower():
            raise RuntimeError("Configure FalkorDB in cloud_config.ini or set FALKORDB_HOST.")
        if not settings["password"] and settings["host"].lower() not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("Set the FalkorDB password in cloud_config.ini or FALKORDB_PASSWORD.")
        client = FalkorDB(
            **{key: settings[key] for key in ("host", "port", "password", "username", "ssl")},
            socket_connect_timeout=5,
            socket_timeout=30,
        )
        self.graph = client.select_graph(settings["graph"])
        self.graph_name = settings["graph"]
        self.llm_configured = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    def _query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return _rows(self.graph.query(cypher, params or {}))

    def _projects(self) -> list[dict[str, Any]]:
        return self._query("MATCH (p:Project) RETURN p.id AS id, p.name AS name, p.status AS status")

    def _is_company_question(self, question: str, last_project_id: str | None) -> bool:
        """Keep company-record questions on FalkorDB; route general knowledge to web search."""
        q = _clean(question)
        if re.search(r"\b(?:PRJ|EMP|DEC|TASK|DOC|MEET)\d+\b", question, re.I):
            return True
        if re.search(r"\b(novatech|company brain|our company|our data|our graph|in the graph|from the graph)\b", q):
            return True

        # Exact project names disambiguate short, natural questions such as “Who owns Atlas Search?”
        try:
            for project in self._projects():
                name = _clean(project.get("name", ""))
                if name and name in q:
                    return True
        except Exception:
            pass

        if last_project_id and re.search(r"\b(it|this project|that project|those tasks|its owner)\b", q):
            return True

        if re.search(r"\b(how many|count|total number|number of|total no)\b", q) and re.search(
            r"\b(projects?|decisions?|employees?|people|tasks?|documents?|meetings?|records?|nodes?|relationships?)\b", q
        ):
            return True
        if re.search(r"\b(how (?:is|are).{0,45}(?:stored|represented)|(?:graph )?schema|node labels?|relationship types?)\b", q):
            return True
        if re.search(r"\b(who (?:owns|made|decided|is assigned|works on|knows)|(?:project|task) (?:owner|status|blocker|dependency)|blocking (?:the )?project|decision maker)\b", q):
            return True
        return False

    @staticmethod
    def _match_project(question: str, projects: list[dict[str, Any]], last_project_id: str | None) -> dict[str, Any] | None:
        q = _clean(question)
        explicit_id = re.search(r"\bPRJ\d+\b", question, re.I)
        if explicit_id:
            wanted = explicit_id.group(0).upper()
            return next((project for project in projects if project.get("id", "").upper() == wanted), None)
        for project in projects:
            name = _clean(project.get("name", ""))
            if name and name in q:
                return project
        q_tokens = set(q.split())
        capitalized_tokens = {
            _clean(token) for token in re.findall(r"\b[A-Z][a-z0-9]+\b", question)
        }
        capitalized_tokens -= {"who", "why", "what", "which", "where", "when", "how", "can", "does", "is", "tell"}
        project_tokens = {
            token
            for item in projects
            for token in _clean(item.get("name", "")).split()
            if token != "expansion"
        }
        use_capitalized_tokens = bool(capitalized_tokens.intersection(project_tokens))
        ranked: list[tuple[float, dict[str, Any]]] = []
        for project in projects:
            name = _clean(project.get("name", ""))
            tokens = [token for token in name.split() if token != "expansion"]
            overlap = (capitalized_tokens if use_capitalized_tokens else q_tokens).intersection(tokens)
            if overlap:
                ranked.append((len(overlap) / max(1, len(tokens)), project))
        if ranked:
            best_score = max(score for score, _ in ranked)
            best = [project for score, project in ranked if score == best_score]
            # The expanded demo graph contains cloned cohorts. If those names match,
            # prefer the canonical original record for ordinary company questions.
            canonical_names = {_clean(p.get("name", "")).removesuffix(" expansion") for p in best}
            threshold = 0.3 if use_capitalized_tokens else 0.5
            if best_score >= threshold and len(canonical_names) == 1:
                return next((p for p in best if "(expansion)" not in str(p.get("name", "")).lower()), best[0])
        contextual_follow_up = bool(
            re.search(r"\b(it|this|that|its|there|same project)\b", q)
            or re.search(r"\b(what about|how about|tell me more)\b", q)
        )
        if last_project_id and contextual_follow_up:
            return next((project for project in projects if project.get("id") == last_project_id), None)
        return None

    def _expertise_topic(self, question: str, project_name: str | None = None) -> str:
        patterns = (
            r"(?:who\s+knows|who\s+has\s+expertise\s+in|who\s+is\s+an?\s+expert\s+in|expertise\s+in|expert\s+in|who\s+can\s+help\s+with)\s+(.+)",
        )
        candidate = ""
        for pattern in patterns:
            match = re.search(pattern, question, re.I)
            if match:
                candidate = match.group(1)
                break
        candidate = re.sub(r"[?!.]+$", "", candidate).strip()
        candidate = re.split(r"\s+(?:and\s+what|and\s+who|and\s+how|for\s+the\s+project)\b|,", candidate, maxsplit=1, flags=re.I)[0].strip()
        if project_name and candidate:
            candidate = re.sub(re.escape(project_name), "", candidate, flags=re.I).strip(" ,;:-")
        candidate = re.sub(r"\b(in|at|for|on)\s*$", "", candidate, flags=re.I).strip()
        return candidate

    def _expert_search(self, topic: str) -> list[dict[str, Any]]:
        return self._query(
            "MATCH (e:Employee)-[:EMPLOYEE_HAS_EXPERTISE]->(x:Expertise) "
            "WHERE toLower(x.name) CONTAINS toLower($topic) "
            "OPTIONAL MATCH (e)-[:EMPLOYEE_BELONGS_TO_TEAM]->(team:Team) "
            "RETURN e.id AS employee_id, e.name AS name, e.title AS title, "
            "team.name AS team, x.name AS expertise ORDER BY e.name LIMIT 20",
            {"topic": topic},
        )

    def _tool_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "list_projects",
                "description": "Find company projects by optional name or status text. Use this to identify project IDs before requesting a dossier.",
                "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Optional words from the project name, description, or status."}}},
            },
            {
                "name": "count_records",
                "description": "Get exact database counts. Use a node label such as Project or Decision, a relationship type, 'nodes', 'relationships', or 'all' for both totals.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "record_type": {
                            "type": "string",
                            "enum": ["all", "nodes", "relationships", *_GRAPH_NODE_SCHEMA.keys(), *_GRAPH_RELATIONSHIP_SCHEMA.keys()],
                            "description": "A graph node label, relationship type, 'nodes', 'relationships', or 'all'.",
                        }
                    },
                    "required": ["record_type"],
                },
            },
            {
                "name": "describe_graph_schema",
                "description": "Explain how data is modeled in FalkorDB: node labels, commonly used fields, relationship directions, and meanings. Use for questions like how decisions are stored or how projects connect to tasks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "about": {
                            "type": "string",
                            "description": "Optional label, relationship, or topic to explain; use 'all' for the complete graph schema.",
                        }
                    },
                },
            },
            {
                "name": "get_project_dossier",
                "description": "Read a project and its linked decisions, owners, meetings, tasks, people, dependencies, and documents by exact project ID.",
                "parameters": {"type": "object", "properties": {"project_id": {"type": "string", "description": "Exact project record ID returned by list_projects."}}, "required": ["project_id"]},
            },
            {
                "name": "find_expertise",
                "description": "Find employees and teams whose expertise matches a topic, such as data lineage or streaming.",
                "parameters": {"type": "object", "properties": {"topic": {"type": "string", "description": "Short skill or expertise phrase."}}, "required": ["topic"]},
            },
            {
                "name": "search_documents",
                "description": "Search document titles and text; optionally narrow results to one exact project ID. Returns source records and linked projects.",
                "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Distinctive words or phrase from the question."}, "project_id": {"type": "string", "description": "Optional exact project ID."}}, "required": ["query"]},
            },
            {
                "name": "search_tasks",
                "description": "Search task titles and optionally restrict to a project. Results include task status, assignees, and linked project IDs.",
                "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Words from the task or work item."}, "project_id": {"type": "string", "description": "Optional exact project ID."}}, "required": ["query"]},
            },
            {
                "name": "get_person_profile",
                "description": "Read an employee's title, team, expertise, owned projects, and assigned tasks by exact employee ID.",
                "parameters": {"type": "object", "properties": {"employee_id": {"type": "string", "description": "Exact employee record ID returned by a graph lookup."}}, "required": ["employee_id"]},
            },
        ]

    def _tool_handlers(self) -> dict[str, Any]:
        return {
            "list_projects": self._tool_list_projects,
            "count_records": self._tool_count_records,
            "describe_graph_schema": self._tool_describe_graph_schema,
            "get_project_dossier": self._tool_get_project_dossier,
            "find_expertise": self._tool_find_expertise,
            "search_documents": self._tool_search_documents,
            "search_tasks": self._tool_search_tasks,
            "get_person_profile": self._tool_get_person_profile,
        }

    def _tool_count_records(self, record_type: str) -> dict[str, Any]:
        """Return exact counts using only fixed, allowlisted Cypher queries."""
        normalized = record_type.strip().upper()
        node_names = {name.upper(): name for name in _GRAPH_NODE_SCHEMA}
        node_names.update({f"{name.upper()}S": name for name in _GRAPH_NODE_SCHEMA if name != "Expertise"})
        node_names["EXPERTISES"] = "Expertise"
        rel_names = {name.upper(): name for name in _GRAPH_RELATIONSHIP_SCHEMA}

        if normalized == "ALL":
            nodes = int(self._query("MATCH (n) RETURN count(n) AS count")[0]["count"])
            relationships = int(self._query("MATCH ()-[r]->() RETURN count(r) AS count")[0]["count"])
            return {
                "record_type": "all",
                "node_count": nodes,
                "relationship_count": relationships,
                "total_records": nodes + relationships,
            }
        if normalized in {"NODE", "NODES"}:
            count = int(self._query("MATCH (n) RETURN count(n) AS count")[0]["count"])
            return {"record_type": "nodes", "count": count}
        if normalized in {"RELATIONSHIP", "RELATIONSHIPS", "EDGES"}:
            count = int(self._query("MATCH ()-[r]->() RETURN count(r) AS count")[0]["count"])
            return {"record_type": "relationships", "count": count}
        if normalized in node_names:
            label = node_names[normalized]
            count = int(self._query(f"MATCH (n:{label}) RETURN count(n) AS count")[0]["count"])
            return {"record_type": label, "kind": "node", "count": count}
        if normalized in rel_names:
            rel_type = rel_names[normalized]
            count = int(self._query(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS count")[0]["count"])
            return {"record_type": rel_type, "kind": "relationship", "count": count}
        raise ValueError("Choose a known graph label, relationship type, 'nodes', 'relationships', or 'all'.")

    def _tool_describe_graph_schema(self, about: str = "all") -> dict[str, Any]:
        """Describe node and relationship types from the project's data model."""
        query = _clean(about)
        if not query or query in {"all", "everything", "schema", "graph"}:
            return {
                "node_types": [{"label": label, **details} for label, details in _GRAPH_NODE_SCHEMA.items()],
                "relationship_types": [
                    {"type": rel_type, **details} for rel_type, details in _GRAPH_RELATIONSHIP_SCHEMA.items()
                ],
            }

        node_types = [
            {"label": label, **details}
            for label, details in _GRAPH_NODE_SCHEMA.items()
            if query in _clean(label)
            or query in _clean(details["description"])
            or any(query in _clean(prop) for prop in details["key_properties"])
        ]
        relationship_types = [
            {"type": rel_type, **details}
            for rel_type, details in _GRAPH_RELATIONSHIP_SCHEMA.items()
            if query in _clean(rel_type)
            or query in _clean(details["meaning"])
            or query in _clean(details["from"])
            or query in _clean(details["to"])
        ]
        return {"about": about, "node_types": node_types, "relationship_types": relationship_types}

    def _tool_list_projects(self, query: str = "") -> list[dict[str, Any]]:
        query = query.strip()[:120]
        projects = self._query(
            "MATCH (p:Project) RETURN p.id AS id, p.name AS name, p.status AS status, "
            "p.description AS description ORDER BY p.name LIMIT 100"
        )
        if query:
            needle = _clean(query)
            projects = [row for row in projects if needle in _clean(" ".join(str(row.get(k, "")) for k in ("name", "status", "description")))]
        return projects[:30]

    def _tool_get_project_dossier(self, project_id: str) -> dict[str, Any]:
        project_id = project_id.strip().upper()
        if not re.fullmatch(r"PRJ\d+", project_id):
            raise ValueError("project_id must be an exact PRJ record ID.")
        dossier = self._project_dossier(project_id)
        # Keep model context focused while the UI still has the full graph data.
        for document in dossier["documents"]:
            document["text"] = str(document.get("text") or "")[:2500]
        return dossier

    def _tool_find_expertise(self, topic: str) -> list[dict[str, Any]]:
        topic = topic.strip()[:100]
        if not topic:
            raise ValueError("topic cannot be empty.")
        return self._expert_search(topic)

    def _tool_search_documents(self, query: str, project_id: str | None = None) -> list[dict[str, Any]]:
        query = query.strip()[:120]
        if not query:
            raise ValueError("query cannot be empty.")
        project_id = project_id.strip().upper() if project_id else None
        if project_id and not re.fullmatch(r"PRJ\d+", project_id):
            raise ValueError("project_id must be an exact PRJ record ID.")
        rows = self._query(
            "MATCH (doc:Document) "
            "WHERE toLower(coalesce(doc.title, '')) CONTAINS toLower($query) "
            "OR toLower(coalesce(doc.text, '')) CONTAINS toLower($query) "
            "OPTIONAL MATCH (doc)-[:DOCUMENT_MENTIONS_PROJECT]->(p:Project) "
            "WITH doc, collect(DISTINCT p.id) AS project_ids, collect(DISTINCT p.name) AS project_names "
            "WHERE $project_id IS NULL OR $project_id IN project_ids "
            "RETURN doc.id AS id, doc.title AS title, doc.status AS status, doc.updated_at AS updated_at, "
            "doc.source_id AS source_id, substring(coalesce(doc.text, ''), 0, 2500) AS text, "
            "project_ids, project_names ORDER BY doc.updated_at DESC LIMIT 10",
            {"query": query, "project_id": project_id},
        )
        return rows

    def _tool_search_tasks(self, query: str, project_id: str | None = None) -> list[dict[str, Any]]:
        query = query.strip()[:120]
        if not query:
            raise ValueError("query cannot be empty.")
        project_id = project_id.strip().upper() if project_id else None
        if project_id and not re.fullmatch(r"PRJ\d+", project_id):
            raise ValueError("project_id must be an exact PRJ record ID.")
        return self._query(
            "MATCH (t:Task) "
            "WHERE toLower(coalesce(t.title, '')) CONTAINS toLower($query) "
            "OR toLower(coalesce(t.description, '')) CONTAINS toLower($query) "
            "OPTIONAL MATCH (p:Project)-[:PROJECT_HAS_TASK]->(t) "
            "WITH t, collect(DISTINCT p.id) AS project_ids, collect(DISTINCT p.name) AS project_names "
            "WHERE $project_id IS NULL OR $project_id IN project_ids "
            "OPTIONAL MATCH (e:Employee)-[:EMPLOYEE_ASSIGNED_TO_TASK]->(t) "
            "RETURN t.id AS id, t.title AS title, t.status AS status, t.priority AS priority, "
            "collect(DISTINCT e.id) AS assignee_ids, collect(DISTINCT e.name) AS assignee_names, "
            "project_ids, project_names ORDER BY t.id LIMIT 15",
            {"query": query, "project_id": project_id},
        )

    def _tool_get_person_profile(self, employee_id: str) -> dict[str, Any]:
        employee_id = employee_id.strip().upper()
        if not re.fullmatch(r"EMP\d+", employee_id):
            raise ValueError("employee_id must be an exact EMP record ID.")
        person = self._query(
            "MATCH (e:Employee {id: $id}) OPTIONAL MATCH (e)-[:EMPLOYEE_BELONGS_TO_TEAM]->(team:Team) "
            "RETURN e.id AS id, e.name AS name, e.title AS title, team.id AS team_id, team.name AS team",
            {"id": employee_id},
        )
        if not person:
            raise LookupError(f"Employee {employee_id} was not found.")
        profile = person[0]
        profile["expertise"] = self._query(
            "MATCH (e:Employee {id: $id})-[:EMPLOYEE_HAS_EXPERTISE]->(x:Expertise) "
            "RETURN collect(DISTINCT {name: x.name}) AS items", {"id": employee_id}
        )[0].get("items", [])
        profile["owned_projects"] = self._query(
            "MATCH (e:Employee {id: $id})-[:EMPLOYEE_OWNS_PROJECT]->(p:Project) "
            "RETURN collect(DISTINCT {id: p.id, name: p.name, status: p.status}) AS items", {"id": employee_id}
        )[0].get("items", [])
        profile["assigned_tasks"] = self._query(
            "MATCH (e:Employee {id: $id})-[:EMPLOYEE_ASSIGNED_TO_TASK]->(t:Task) "
            "RETURN collect(DISTINCT {id: t.id, title: t.title, status: t.status}) AS items", {"id": employee_id}
        )[0].get("items", [])
        return profile

    def _project_dossier(self, project_id: str) -> dict[str, Any]:
        project = self._query(
            "MATCH (p:Project {id: $id}) RETURN p.id AS id, p.name AS name, p.status AS status, "
            "p.description AS description, p.blockers AS blockers, p.deadline AS deadline, p.risks AS risks",
            {"id": project_id},
        )
        if not project:
            raise LookupError(f"Project {project_id} is not present in the graph.")

        decisions = self._query(
            "MATCH (p:Project {id: $id})-[:PROJECT_BLOCKED_BY_DECISION]->(d:Decision) "
            "OPTIONAL MATCH (d)-[:DECISION_MADE_BY_EMPLOYEE]->(owner:Employee) "
            "OPTIONAL MATCH (meeting:Meeting)-[:MEETING_MADE_DECISION]->(d) "
            "RETURN d.id AS id, d.title AS title, d.description AS description, d.status AS status, "
            "owner.id AS owner_id, owner.name AS owner_name, owner.title AS owner_title, "
            "meeting.id AS meeting_id, meeting.title AS meeting_title, meeting.date AS meeting_date, "
            "meeting.text AS meeting_source ORDER BY d.id",
            {"id": project_id},
        )
        tasks = self._query(
            "MATCH (p:Project {id: $id})-[:PROJECT_HAS_TASK]->(t:Task) "
            "OPTIONAL MATCH (e:Employee)-[:EMPLOYEE_ASSIGNED_TO_TASK]->(t) "
            "OPTIONAL MATCH (t)-[:TASK_BLOCKED_BY_TASK]->(blocked:Task) "
            "RETURN t.id AS id, t.title AS title, t.status AS status, t.priority AS priority, "
            "e.id AS assignee_id, e.name AS assignee_name, collect(DISTINCT blocked.id) AS blocked_by "
            "ORDER BY t.id",
            {"id": project_id},
        )
        dependencies = self._query(
            "MATCH (p:Project {id: $id})-[:PROJECT_DEPENDS_ON_PROJECT]->(other:Project) "
            "RETURN other.id AS id, other.name AS name, other.status AS status, 'upstream' AS direction "
            "UNION "
            "MATCH (other:Project)-[:PROJECT_DEPENDS_ON_PROJECT]->(p:Project {id: $id}) "
            "RETURN other.id AS id, other.name AS name, other.status AS status, 'downstream' AS direction",
            {"id": project_id},
        )
        documents = self._query(
            "MATCH (doc:Document)-[:DOCUMENT_MENTIONS_PROJECT]->(p:Project {id: $id}) "
            "RETURN doc.id AS id, doc.title AS title, doc.status AS status, "
            "doc.updated_at AS updated_at, doc.source_id AS source_id, doc.text AS text",
            {"id": project_id},
        )
        people = self._query(
            "MATCH (e:Employee)-[:EMPLOYEE_OWNS_PROJECT]->(p:Project {id: $id}) "
            "OPTIONAL MATCH (e)-[:EMPLOYEE_HAS_EXPERTISE]->(x:Expertise) "
            "RETURN e.id AS id, e.name AS name, e.title AS title, 'project owner' AS role, "
            "collect(DISTINCT x.name) AS expertise "
            "UNION "
            "MATCH (e:Employee)-[:EMPLOYEE_ASSIGNED_TO_TASK]->(t:Task)<-[:PROJECT_HAS_TASK]-(p:Project {id: $id}) "
            "OPTIONAL MATCH (e)-[:EMPLOYEE_HAS_EXPERTISE]->(x:Expertise) "
            "RETURN e.id AS id, e.name AS name, e.title AS title, 'task contributor' AS role, "
            "collect(DISTINCT x.name) AS expertise",
            {"id": project_id},
        )
        for decision in decisions:
            if decision.get("owner_id"):
                decision["owner_expertise"] = self._query(
                    "MATCH (e:Employee {id: $id})-[:EMPLOYEE_HAS_EXPERTISE]->(x:Expertise) "
                    "RETURN collect(DISTINCT x.name) AS expertise",
                    {"id": decision["owner_id"]},
                )[0].get("expertise", [])
        status_order = {"current": 0, "draft": 1, "superseded": 2}
        documents.sort(key=lambda doc: (status_order.get(str(doc.get("status", "")).lower(), 3), str(doc.get("updated_at", ""))))
        return {
            "project": project[0],
            "decisions": decisions,
            "tasks": tasks,
            "dependencies": dependencies,
            "documents": documents,
            "people": people,
        }

    def answer(self, question: str, last_project_id: str | None = None) -> dict[str, Any]:
        question = question.strip()
        if not question:
            raise ValueError("Ask a question about a project, person, decision, dependency, or document.")
        if not self._is_company_question(question, last_project_id):
            if self.llm_configured:
                web_result = run_web_search_agent(question)
                if web_result:
                    return {
                        "question": question,
                        **web_result,
                        "answer_mode": "Web search agent",
                        "llm_configured": True,
                        "plan": [{"tool": "google_search", "why": "Search the web and cite claims using Gemini grounding metadata."}],
                        "tool_results": [],
                        "project": None,
                        "dossier": None,
                        "experts": [],
                        "sources": [],
                    }
            return {
                "question": question,
                "answer": "This looks like a general question, but web search is unavailable. Configure a Gemini API key to answer it with citations. For company information, ask about a project, person, decision, task, or document in the NovaTech graph.",
                "answer_mode": "Web search unavailable",
                "llm_configured": self.llm_configured,
                "plan": [],
                "tool_results": [],
                "project": None,
                "dossier": None,
                "experts": [],
                "sources": [],
            }
        if self.llm_configured:
            agent_result = run_tool_calling_agent(question, self._tool_specs(), self._tool_handlers())
            if agent_result:
                dossier = next(
                    (item.get("result") for item in agent_result["tool_results"]
                     if item.get("tool") == "get_project_dossier" and item.get("result")),
                    None,
                )
                experts = next(
                    (item.get("result") for item in agent_result["tool_results"]
                     if item.get("tool") == "find_expertise" and isinstance(item.get("result"), list)),
                    [],
                )
                if dossier:
                    dossier["expert_matches"] = experts
                return {
                    "question": question,
                    "answer": agent_result["answer"],
                    "answer_mode": "Gemini tool agent",
                    "llm_configured": True,
                    "plan": agent_result["plan"],
                    "tool_results": agent_result["tool_results"],
                    "project": dossier.get("project") if dossier else None,
                    "dossier": dossier,
                    "experts": experts,
                    "expertise_topic": None,
                    "sources": agent_result["sources"],
                    "model": agent_result["model"],
                    "citation_validation": agent_result.get("citation_validation"),
                }
            fallback = self._answer_deterministic(question, last_project_id)
            fallback["answer_mode"] = "Deterministic fallback"
            fallback["llm_configured"] = True
            fallback["fallback_reason"] = "Gemini did not return a validated tool-call answer."
            return fallback
        return self._answer_deterministic(question, last_project_id)

    def _answer_deterministic(self, question: str, last_project_id: str | None = None) -> dict[str, Any]:
        question = question.strip()
        if not question:
            raise ValueError("Ask a question about a project, person, decision, dependency, or document.")
        projects = self._projects()
        project = self._match_project(question, projects, last_project_id)
        expertise_topic = self._expertise_topic(question, project.get("name") if project else None)
        people_intent = bool(re.search(r"\b(who|expert|expertise|knows|help)\b", question, re.I))
        plan = [{"tool": "resolve_project", "why": "Match the question to a company project in FalkorDB."}]

        if not project and people_intent and expertise_topic:
            plan.append({"tool": "find_expertise", "why": f"Find employees connected to {expertise_topic} expertise."})
            matches = self._expert_search(expertise_topic)
            answer = (
                f"I found {len(matches)} colleague{'s' if len(matches) != 1 else ''} linked to **{expertise_topic}** expertise."
                if matches else f"I couldn’t find a colleague linked to **{expertise_topic}** in the graph."
            )
            evidence = {"expertise_topic": expertise_topic, "experts": matches}
            citations = list(dict.fromkeys(
                [str(row.get("employee_id")) for row in matches if row.get("employee_id")]
                + ["Expertise"]
            ))
            return {"question": question, "answer": answer, "plan": plan, "project": None,
                    "expertise_topic": expertise_topic, "experts": matches, "sources": citations,
                    "answer_mode": "Deterministic fallback", "llm_configured": self.llm_configured}

        if not project:
            examples = ", ".join(f"{p['name']} ({p['id']})" for p in projects[:8])
            return {"question": question,
                    "answer": "I couldn’t identify a project or expertise topic in that question. Try naming one of these projects: " + examples,
                    "plan": plan, "project": None, "sources": []}

        plan.extend([
            {"tool": "trace_decision", "why": "Follow project → blocking decision → decision maker → meeting."},
            {"tool": "inspect_work", "why": "Follow project → tasks, contributors, and dependency edges."},
            {"tool": "retrieve_sources", "why": "Read linked documents and rank current guidance ahead of historical records."},
        ])
        dossier = self._project_dossier(project["id"])
        if people_intent and expertise_topic:
            plan.append({"tool": "find_expertise", "why": f"Search company expertise for {expertise_topic}."})
            dossier["expert_matches"] = self._expert_search(expertise_topic)
        return {
            "question": question,
            "answer": self._compose_answer(dossier),
            "answer_mode": "Deterministic fallback",
            "llm_configured": self.llm_configured,
            "plan": plan,
            "project": dossier["project"],
            "dossier": dossier,
            "expertise_topic": expertise_topic,
            "sources": self._source_ids(dossier),
        }

    @staticmethod
    def _source_ids(dossier: dict[str, Any]) -> list[str]:
        ids = [dossier["project"].get("id")]
        for section, key in (("decisions", "id"), ("tasks", "id"), ("documents", "id"), ("people", "id"), ("dependencies", "id")):
            ids.extend(row.get(key) for row in dossier.get(section, []))
        return list(dict.fromkeys(value for value in ids if value))

    @staticmethod
    def _compose_answer(dossier: dict[str, Any]) -> str:
        project = dossier["project"]
        decisions = dossier["decisions"]
        lines = [f"**{project.get('name')}** is **{project.get('status', 'unknown').replace('_', ' ')}**."]
        blockers = project.get("blockers") or []
        if isinstance(blockers, str):
            blockers = [blockers]
        if blockers:
            lines.append("**Blocker:** " + "; ".join(str(item) for item in blockers) + f" `[{project.get('id')}]`")
        for decision in decisions:
            why = decision.get("description") or decision.get("title") or "A linked decision is recorded."
            lines.append(f"**Decision:** {why} `[{decision.get('id')}]`")
            if decision.get("owner_name"):
                expertise = ", ".join(decision.get("owner_expertise") or [])
                detail = f" ({expertise})" if expertise else ""
                lines.append(
                    f"**Decision owner:** {decision['owner_name']} · {decision.get('owner_title', 'role unavailable')}{detail} "
                    f"`[{decision.get('owner_id')}]`"
                )
            if decision.get("meeting_title"):
                lines.append(
                    f"**Recorded in:** {decision['meeting_title']} · {decision.get('meeting_date', 'date unavailable')} "
                    f"`[{decision.get('meeting_id')}]`"
                )
        upstream = [row for row in dossier["dependencies"] if row.get("direction") == "upstream"]
        downstream = [row for row in dossier["dependencies"] if row.get("direction") == "downstream"]
        if upstream:
            lines.append("**Depends on:** " + ", ".join(f"{row.get('name')} ({row.get('status')}) `[{row.get('id')}]`" for row in upstream))
        if downstream:
            lines.append("**Projects affected downstream:** " + ", ".join(f"{row.get('name')} ({row.get('status')}) `[{row.get('id')}]`" for row in downstream))
        project_owners = [person for person in dossier["people"] if person.get("role") == "project owner"]
        if project_owners:
            lines.append("**Project owner:** " + ", ".join(f"{person.get('name')} · {person.get('title')} `[{person.get('id')}]`" for person in project_owners))
        blocked = [task for task in dossier["tasks"] if str(task.get("status", "")).lower() == "blocked"]
        if blocked:
            lines.append("**Blocked work:** " + ", ".join(f"{task.get('title')} `[{task.get('id')}]`" for task in blocked))
        current_docs = [doc for doc in dossier["documents"] if str(doc.get("status", "")).lower() == "current"]
        historical_docs = [doc for doc in dossier["documents"] if str(doc.get("status", "")).lower() in {"draft", "superseded"}]
        if current_docs:
            lines.append("**Current guidance:** " + "; ".join(f"{doc.get('title')} · updated {doc.get('updated_at', 'date unavailable')} `[{doc.get('id')}]`" for doc in current_docs))
        if historical_docs:
            lines.append("**Historical guidance:** " + "; ".join(f"{doc.get('title')} ({doc.get('status')}) `[{doc.get('id')}]`" for doc in historical_docs))
        return "\n\n".join(lines)
