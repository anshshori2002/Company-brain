"""Streamlit interface for the Gemini tool-calling NovaTech Company Brain."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import streamlit as st

from agent import CompanyBrainAgent
from logging_service import AgentLoggingService

ROOT = Path(__file__).resolve().parent
SCENARIOS_PATH = ROOT.parent / "data" / "scenarios.json"
GEMINI_READY = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

TOOL_HELP = {
    "list_projects": "Find projects by name or status.",
    "count_records": "Get exact node, relationship, or graph-wide counts.",
    "describe_graph_schema": "Explain node types, common fields, and how graph relationships are stored.",
    "get_project_dossier": "Follow a project through decisions, owners, work, dependencies, and documents.",
    "find_expertise": "Find colleagues by expertise.",
    "search_documents": "Search source document text.",
    "search_tasks": "Search task titles and status.",
    "get_person_profile": "Look up an employee's team, skills, projects, and assigned work.",
}

st.set_page_config(page_title="NovaTech Company Brain", page_icon="🧠", layout="wide")
st.markdown(
    """
    <style>
    .block-container { max-width: 1120px; padding-top: 2rem; padding-bottom: 3rem; }
    [data-testid="stChatMessage"] { border: 1px solid rgba(128,128,128,.16); border-radius: 14px; }
    .hero-caption { color: #777; margin-top: -0.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def get_agent() -> CompanyBrainAgent:
    return CompanyBrainAgent()


@st.cache_resource(show_spinner=False)
def get_logging_service() -> AgentLoggingService:
    return AgentLoggingService()


def run_question(question: str) -> None:
    started = time.perf_counter()
    busy_message = "The agent is choosing a source and gathering evidence…" if GEMINI_READY else "Gathering evidence from FalkorDB…"
    with st.spinner(busy_message):
        try:
            agent = get_agent()
            result = agent.answer(question, st.session_state.get("last_project_id"))
        except Exception as exc:
            try:
                get_logging_service().log_error(question, exc, (time.perf_counter() - started) * 1000)
            except OSError:
                pass
            st.error(f"The Company Brain could not answer from FalkorDB: {exc}")
            st.info("Check that the local FalkorDB container is running and the `novatech` graph is loaded.")
            return
    try:
        result["event_id"] = get_logging_service().log_turn(
            question, result, (time.perf_counter() - started) * 1000
        )
    except OSError:
        result["event_id"] = None
    if result.get("project"):
        st.session_state["last_project_id"] = result["project"]["id"]
    st.session_state.setdefault("conversation", []).append({"question": question, "result": result})


def render_table(rows: Any) -> None:
    if isinstance(rows, list) and rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No matching records were returned by this lookup.")


def render_dossier(dossier: dict[str, Any]) -> None:
    project = dossier["project"]
    metrics = st.columns(3)
    metrics[0].metric("Project", project.get("id", "—"))
    metrics[1].metric("Status", str(project.get("status", "Unknown")).replace("_", " ").title())
    metrics[2].metric("Linked sources", len(dossier.get("documents", [])))

    with st.expander("Decision and ownership", expanded=True):
        if dossier.get("decisions"):
            render_table(dossier["decisions"])
        else:
            st.caption("No linked decisions were found.")
        if dossier.get("people"):
            st.markdown("**Owners and contributors**")
            render_table(dossier["people"])

    with st.expander("Tasks and dependencies"):
        left, right = st.columns(2)
        with left:
            st.markdown("**Tasks**")
            render_table(dossier.get("tasks", []))
        with right:
            st.markdown("**Dependencies**")
            render_table(dossier.get("dependencies", []))

    with st.expander("Source documents"):
        docs = dossier.get("documents", [])
        if docs:
            render_table([
                {key: doc.get(key) for key in ("id", "title", "status", "updated_at", "source_id")}
                for doc in docs
            ])
            for doc in docs:
                with st.expander(f"{doc.get('title')} · {doc.get('status')} · {doc.get('id')}"):
                    st.caption(f"Source: {doc.get('source_id', 'not recorded')} · Updated: {doc.get('updated_at', 'date unavailable')}")
                    st.text(doc.get("text") or "Document text unavailable.")
        else:
            st.caption("No documents are linked to this project.")


def render_tool_trace(result: dict[str, Any]) -> None:
    trace = result.get("plan", [])
    evidence = result.get("tool_results", [])
    with st.expander("Agent activity · tools and evidence", expanded=result.get("answer_mode") == "Gemini tool agent"):
        if trace:
            for index, call in enumerate(trace, start=1):
                st.markdown(f"**{index}. `{call.get('tool', 'tool')}`** — {call.get('why', '')}")
                if call.get("arguments"):
                    st.code(json.dumps(call["arguments"], ensure_ascii=False, indent=2), language="json")
        else:
            st.caption("No graph tool calls were recorded.")

        if evidence:
            st.markdown("**Returned records**")
            for index, item in enumerate(evidence, start=1):
                name = item.get("tool", "tool")
                payload = item.get("result", item.get("error"))
                if name == "get_project_dossier" and isinstance(payload, dict):
                    st.caption(f"{name}: project dossier retrieved")
                elif isinstance(payload, list):
                    with st.expander(f"{name} · {len(payload)} record(s)"):
                        render_table(payload)
                elif isinstance(payload, dict):
                    with st.expander(f"{name} · profile/result"):
                        st.json(payload)
                elif item.get("error"):
                    st.warning(f"{name}: {item['error']}")

        if result.get("sources"):
            st.markdown("**Cited graph record IDs**")
            st.caption(" · ".join(f"`{source}`" for source in result["sources"]))


with st.sidebar:
    st.title("🧠 Company Brain")
    st.caption("NovaTech · FalkorDB graph")
    st.divider()
    st.markdown("**Agent mode**")
    if GEMINI_READY:
        st.success("Gemini graph tools and web search are enabled", icon="✨")
        st.caption("Company questions use read-only FalkorDB lookups; general questions use Google Search grounding with citations.")
    else:
        st.info("Graph-backed fallback mode", icon="🔎")
        st.caption("Add a Gemini key to the local `.env` file to enable model-selected tools.")
    st.divider()
    st.markdown("**Available graph tools**")
    for tool_name, description in TOOL_HELP.items():
        st.markdown(f"- `{tool_name}`  \n  {description}")
    st.divider()
    if st.button("Start a new conversation", use_container_width=True):
        st.session_state["conversation"] = []
        st.session_state.pop("last_project_id", None)
        st.rerun()
    with st.expander("Evaluation & logs"):
        metrics = get_logging_service().summary()
        st.caption("Local agent run metrics and user ratings")
        metric_cols = st.columns(2)
        metric_cols[0].metric("Logged turns", metrics["turns"])
        metric_cols[1].metric("Gemini tool-agent turns", metrics["gemini_turns"])
        st.metric("Web-search turns", metrics["web_search_turns"])
        metric_cols = st.columns(2)
        metric_cols[0].metric("Average response time", f"{metrics['avg_latency_ms']} ms")
        metric_cols[1].metric("Average tools per turn", metrics["avg_tool_calls"])
        metric_cols = st.columns(2)
        metric_cols[0].metric("Fallback turns", metrics["fallback_turns"])
        metric_cols[1].metric("Tool/system errors", metrics["errors"] + metrics["tool_errors"])
        if metrics["citation_validation_rate"] is not None:
            st.metric("Gemini citation validation", f"{metrics['citation_validation_rate']}%")
        if metrics["citation_id_match_rate"] is not None:
            st.metric("Citations matched returned IDs", f"{metrics['citation_id_match_rate']}%")
        if metrics["positive_feedback_rate"] is not None:
            st.metric("Positive feedback", f"{metrics['positive_feedback_rate']}%", help=f"Based on {metrics['feedback_count']} ratings")
        st.caption(f"Content logging: {'on' if metrics['content_logging'] else 'metadata only'} · {metrics['log_path']}")

st.title("Ask your company brain")
st.markdown(
    '<p class="hero-caption">Ask about company records for graph-grounded answers, or general questions for web search with citations.</p>',
    unsafe_allow_html=True,
)

try:
    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    scenarios = []

with st.expander("Try a challenge question", expanded=not st.session_state.get("conversation")):
    if scenarios:
        scenario = st.selectbox(
            "Choose a sample investigation",
            scenarios,
            format_func=lambda row: row["question"],
            label_visibility="collapsed",
        )
        if st.button("Investigate this question", type="secondary"):
            run_question(scenario["question"])

with st.form("ask_company_brain", clear_on_submit=True):
    question = st.text_input(
        "Your question",
        placeholder="What is blocking Drift Data Mesh, who can resolve it, and which current documents explain why?",
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("Ask the Company Brain", type="primary", use_container_width=True)
if submitted and question.strip():
    run_question(question)

conversation = st.session_state.get("conversation", [])
for turn in conversation:
    with st.chat_message("user"):
        st.markdown(turn["question"])
    result = turn["result"]
    with st.chat_message("assistant", avatar="🧠"):
        st.markdown(result["answer"])
        if result.get("answer_mode") == "Web search agent":
            st.caption(f"Web search agent · {result.get('model', 'Gemini')} · citations from Google Search grounding")
            if result.get("web_sources"):
                st.markdown("**Web sources**")
                for index, source in enumerate(result["web_sources"], start=1):
                    st.markdown(f"{index}. [{source.get('title') or source.get('url')}]({source.get('url')})")
        elif result.get("answer_mode") == "Web search unavailable":
            st.caption("Web search unavailable · add a Gemini API key for general questions")
        elif result.get("answer_mode") == "Gemini tool agent":
            st.caption(f"Gemini agent · {result.get('model', 'Gemini')} · grounded in retrieved records")
        elif result.get("llm_configured"):
            st.caption("Graph-grounded fallback · Gemini could not complete a cited tool-call answer")
        else:
            st.caption("Graph-grounded answer")

        event_id = result.get("event_id")
        if event_id:
            rating = st.feedback("thumbs", key=f"answer_feedback_{event_id}")
            if rating is not None and not result.get("feedback_recorded"):
                try:
                    get_logging_service().log_feedback(event_id, "up" if rating == 1 else "down")
                    result["feedback_recorded"] = True
                    st.toast("Thanks — your rating was added to the local evaluation log.")
                except OSError:
                    st.caption("Could not save this rating to the local evaluation log.")

        if result.get("experts"):
            st.markdown("**Colleagues with matching expertise**")
            render_table(result["experts"])

        render_tool_trace(result)

        dossier = result.get("dossier")
        if dossier:
            render_dossier(dossier)

if not conversation:
    st.info("Try a sample investigation or ask a question in your own words. The agent will choose graph tools and show its evidence.")
