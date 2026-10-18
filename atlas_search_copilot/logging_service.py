"""Local structured logging and lightweight evaluation for agent turns."""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from statistics import mean
from typing import Any


_CITATION = re.compile(r"\[([A-Za-z0-9_-]+)\]")


class AgentLoggingService:
    """Append local JSONL events without duplicating raw graph result payloads."""

    def __init__(self, log_dir: Path | None = None) -> None:
        self.log_dir = log_dir or Path(__file__).resolve().parent / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.log_dir / "agent_events.jsonl"
        self.capture_text = os.getenv("COMPANY_BRAIN_LOG_CONTENT", "true").lower() not in {"0", "false", "no"}
        self.logger = logging.getLogger("company_brain.agent_events")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if not self.logger.handlers:
            handler = RotatingFileHandler(
                self.path,
                maxBytes=3_000_000,
                backupCount=4,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    def _write(self, event: dict[str, Any]) -> None:
        event["schema_version"] = 1
        self.logger.info(json.dumps(event, ensure_ascii=False, default=str))

    def log_turn(self, question: str, result: dict[str, Any], latency_ms: float) -> str:
        event_id = str(uuid.uuid4())
        plan = result.get("plan", [])
        tool_results = result.get("tool_results", [])
        sources = list(result.get("sources", []))
        cited = list(dict.fromkeys(_CITATION.findall(result.get("answer", ""))))
        outputs = []
        for item in tool_results:
            value = item.get("result")
            outputs.append({
                "tool": item.get("tool", "unknown"),
                "record_count": len(value) if isinstance(value, list) else int(bool(value)),
                "error": bool(item.get("error")),
            })
        event: dict[str, Any] = {
            "event": "agent_turn",
            "event_id": event_id,
            "timestamp": self._now(),
            "answer_mode": result.get("answer_mode", "unknown"),
            "model": result.get("model"),
            "latency_ms": round(max(0.0, latency_ms), 2),
            "tool_calls": [
                {
                    "name": step.get("tool"),
                    "arguments": step.get("arguments", {}) if self.capture_text else {
                        "provided_fields": sorted((step.get("arguments") or {}).keys())
                    },
                }
                for step in plan
            ],
            "tool_outputs": outputs,
            "tool_error_count": sum(1 for item in outputs if item["error"]),
            "fallback_reason": result.get("fallback_reason"),
            "source_ids": sources,
            "answer_citations": cited,
            "citation_validation": result.get("citation_validation"),
            "citation_ids_returned": set(cited).issubset(set(sources)),
        }
        if self.capture_text:
            event["question"] = question
            event["answer"] = result.get("answer", "")
        self._write(event)
        return event_id

    def log_error(self, question: str, error: Exception, latency_ms: float) -> str:
        event_id = str(uuid.uuid4())
        event: dict[str, Any] = {
            "event": "agent_error",
            "event_id": event_id,
            "timestamp": self._now(),
            "error_type": type(error).__name__,
            "latency_ms": round(max(0.0, latency_ms), 2),
        }
        if self.capture_text:
            event["question"] = question
        self._write(event)
        return event_id

    def log_feedback(self, event_id: str, rating: str) -> None:
        if rating not in {"up", "down"}:
            raise ValueError("rating must be 'up' or 'down'.")
        self._write({
            "event": "user_feedback",
            "event_id": str(uuid.uuid4()),
            "turn_event_id": event_id,
            "timestamp": self._now(),
            "rating": rating,
        })

    def summary(self) -> dict[str, Any]:
        events: list[dict[str, Any]] = []
        for path in self.log_dir.glob("agent_events.jsonl*"):
            try:
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            except OSError:
                continue

        turns = [event for event in events if event.get("event") == "agent_turn"]
        errors = [event for event in events if event.get("event") == "agent_error"]
        tool_errors = sum(event.get("tool_error_count", 0) for event in turns)
        feedback = [event for event in events if event.get("event") == "user_feedback"]
        model_turns = [event for event in turns if event.get("answer_mode") == "Gemini tool agent"]
        validated = [event for event in model_turns if event.get("citation_validation") is not None]
        feedback_up = sum(1 for event in feedback if event.get("rating") == "up")
        feedback_count = sum(1 for event in feedback if event.get("rating") in {"up", "down"})
        return {
            "turns": len(turns),
            "errors": len(errors),
            "tool_errors": tool_errors,
            "gemini_turns": len(model_turns),
            "fallback_turns": sum(1 for event in turns if "fallback" in str(event.get("answer_mode", "")).lower()),
            "avg_latency_ms": round(mean(event.get("latency_ms", 0) for event in turns), 1) if turns else 0,
            "avg_tool_calls": round(mean(len(event.get("tool_calls", [])) for event in turns), 1) if turns else 0,
            "citation_validation_rate": round(
                mean(bool(event.get("citation_validation")) for event in validated) * 100, 1
            ) if validated else None,
            "citation_id_match_rate": round(
                mean(bool(event.get("citation_ids_returned")) for event in model_turns) * 100, 1
            ) if model_turns else None,
            "feedback_count": feedback_count,
            "positive_feedback_rate": round(feedback_up / feedback_count * 100, 1) if feedback_count else None,
            "log_path": str(self.path),
            "content_logging": self.capture_text,
        }
