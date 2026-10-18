#!/usr/bin/env python3
"""Validate generated NovaTech records, references, graph paths, and scenario evidence."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

STATUSES={"projects":{"on_track","at_risk","delayed","completed"},"tasks":{"todo","in_progress","blocked","done"},"decisions":{"approved","active","rejected","superseded"},"documents":{"current","draft","superseded"}}
REQUIRED={"EMPLOYEE_BELONGS_TO_TEAM","EMPLOYEE_OWNS_PROJECT","EMPLOYEE_ASSIGNED_TO_TASK","PROJECT_HAS_TASK","PROJECT_DEPENDS_ON_PROJECT","TASK_BLOCKED_BY_TASK","MEETING_MADE_DECISION","DECISION_AFFECTS_PROJECT","DECISION_MADE_BY_EMPLOYEE","DOCUMENT_MENTIONS_PROJECT","EMPLOYEE_HAS_EXPERTISE","PROJECT_BLOCKED_BY_DECISION"}

def read_json(p: Path):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc: raise ValueError(f"Cannot read {p}: {exc}")

def date_ok(value):
    if not isinstance(value,str): return False
    try: datetime.fromisoformat(value.replace("Z","+00:00")); return True
    except ValueError: return False

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("--data-dir",type=Path,default=Path(__file__).resolve().parents[1]/"data"); args=ap.parse_args(); root=args.data_dir.resolve()
    errors=[]; warnings=[]
    def load(name):
        try:return read_json(root/name)
        except Exception as e: errors.append(str(e)); return []
    teams=load("teams.json"); projects=load("projects.json"); tasks=load("tasks.json"); decisions=load("decisions.json"); scenarios=load("scenarios.json"); rel=load("relationships.json"); manifest=load("manifest.json")
    try:
        with (root/"employees.csv").open(newline="",encoding="utf-8") as f:
            employees=[]
            for row in csv.DictReader(f):
                row["expertise"]=[x.strip() for x in row["expertise"].split(";") if x.strip()]; employees.append(row)
    except Exception as e: employees=[]; errors.append(f"Cannot read employees.csv: {e}")
    meetings=[]
    for path in sorted((root/"meetings").glob("meeting_*.md")) if (root/"meetings").exists() else []:
        body=path.read_text(encoding="utf-8"); m=re.search(r"^- Meeting ID: (\S+)$",body,re.M); dt=re.search(r"^- Date: (\S+)$",body,re.M)
        if not m or not dt: errors.append(f"{path.name}: missing meeting ID/date metadata")
        else: meetings.append({"id":m.group(1),"date":dt.group(1),"body":body,"path":path})
    docs=[]
    for path in sorted((root/"documents").glob("policy_*.md")) if (root/"documents").exists() else []:
        body=path.read_text(encoding="utf-8"); m=re.search(r"^- Document ID: (\S+)$",body,re.M); sid=re.search(r"^- Source ID: (\S+)$",body,re.M); status=re.search(r"^- Status: (\S+)$",body,re.M); updated=re.search(r"^- Updated: (\S+)$",body,re.M)
        if not m or not sid or not status or not updated: errors.append(f"{path.name}: missing document ID, source ID, status, or update timestamp")
        else: docs.append({"id":m.group(1),"source_id":sid.group(1),"status":status.group(1),"updated_at":updated.group(1),"body":body,"path":path})
    entities={"employees":employees,"teams":teams,"projects":projects,"tasks":tasks,"decisions":decisions,"meetings":meetings,"documents":docs}
    ids={};
    for kind,records in entities.items():
        seen=set()
        for n,item in enumerate(records):
            ident=item.get("id")
            if not ident: errors.append(f"{kind}[{n}] missing ID")
            elif ident in seen: errors.append(f"{kind}: duplicate ID {ident}")
            seen.add(ident)
        ids[kind]=seen
    exp_nodes={x.get("id") for x in manifest.get("expertise_nodes",[]) if x.get("id")}
    all_ids=set().union(*ids.values(),exp_nodes)
    required_fields={"employees":{"name","team_id","expertise","created_at","updated_at"},"teams":{"name","description","created_at"},"projects":{"name","team_id","owner_id","status","status_history","deadline","created_at","updated_at"},"tasks":{"title","project_id","assignee_id","status","due_date","created_at","updated_at"},"decisions":{"title","status","meeting_id","made_by_id","affected_project_ids","created_at","updated_at"}}
    for kind,fields in required_fields.items():
        for item in entities[kind]:
            for field in fields:
                if field not in item or item[field] in (None,""): errors.append(f"{item.get('id','?')} missing required field {field}")
    dates_fields={"employees":["created_at","updated_at"],"teams":["created_at"],"projects":["deadline","created_at","updated_at"],"tasks":["due_date","created_at","updated_at"],"decisions":["created_at","updated_at"],"meetings":["date"],"documents":["updated_at"]}
    for kind,fields in dates_fields.items():
        for item in entities[kind]:
            for field in fields:
                if not date_ok(item.get(field)): errors.append(f"{item.get('id','?')} has invalid {field}: {item.get(field)}")
    for kind,records in [("projects",projects),("tasks",tasks),("decisions",decisions),("documents",docs)]:
        status_set=STATUSES[kind]
        for item in records:
            if item.get("status") not in status_set: errors.append(f"{item.get('id','?')} has invalid {kind} status {item.get('status')}")
    for p in projects:
        history=p.get("status_history",[])
        if not history or history[-1].get("status")!=p.get("status"): errors.append(f"{p.get('id','?')} status history does not end at current status")
        for event in history:
            if event.get("status") not in STATUSES["projects"]: errors.append(f"{p.get('id','?')} has invalid historical project status {event.get('status')}")
            if not date_ok(event.get("changed_at")): errors.append(f"{p.get('id','?')} has invalid status change timestamp")
    # Count assertions follow the generation manifest, and exact defaults are surfaced explicitly.
    count_map={"employees":len(employees),"teams":len(teams),"projects":len(projects),"meetings":len(meetings),"decisions":len(decisions),"tasks":len(tasks),"documents":len(docs)}
    expected=manifest.get("counts",{})
    for k,v in count_map.items():
        if expected.get(k)!=v: errors.append(f"Count mismatch for {k}: manifest={expected.get(k)} found={v}")
    defaults={"employees":20,"teams":5,"projects":10,"meetings":30,"decisions":30,"tasks":50,"documents":15}
    if expected!=defaults: warnings.append(f"Configured counts {expected}; default target counts are {defaults}.")

    endpoint_kinds={"EMPLOYEE_BELONGS_TO_TEAM":("employees","teams"),"EMPLOYEE_OWNS_PROJECT":("employees","projects"),"EMPLOYEE_ASSIGNED_TO_TASK":("employees","tasks"),"PROJECT_HAS_TASK":("projects","tasks"),"PROJECT_DEPENDS_ON_PROJECT":("projects","projects"),"TASK_BLOCKED_BY_TASK":("tasks","tasks"),"MEETING_MADE_DECISION":("meetings","decisions"),"DECISION_AFFECTS_PROJECT":("decisions","projects"),"DECISION_MADE_BY_EMPLOYEE":("decisions","employees"),"DOCUMENT_MENTIONS_PROJECT":("documents","projects"),"EMPLOYEE_HAS_EXPERTISE":("employees","expertise"),"PROJECT_BLOCKED_BY_DECISION":("projects","decisions")}
    graph=defaultdict(set); edge_types=set()
    for i,e in enumerate(rel):
        typ=e.get("type"); src=e.get("source_id"); dst=e.get("target_id"); edge_types.add(typ)
        if typ not in endpoint_kinds: errors.append(f"Relationship {i} has unknown type {typ}"); continue
        left,right=endpoint_kinds[typ]
        if src not in ids[left]: errors.append(f"{typ} source does not resolve: {src}")
        target_set=exp_nodes if right=="expertise" else ids[right]
        if dst not in target_set: errors.append(f"{typ} target does not resolve: {dst}")
        if src and dst: graph[src].add(dst); graph[dst].add(src)
    for typ in sorted(REQUIRED-edge_types): errors.append(f"Missing required relationship type {typ}")
    # Validate embedded foreign keys too, so an omitted edge cannot hide a broken record.
    for e in employees:
        if e.get("team_id") not in ids["teams"]: errors.append(f"{e['id']} references missing team {e.get('team_id')}")
    for p in projects:
        for field,target in [("team_id","teams"),("owner_id","employees")]:
            if p.get(field) not in ids[target]: errors.append(f"{p['id']} references missing {field} {p.get(field)}")
    for t in tasks:
        for field,target in [("project_id","projects"),("assignee_id","employees")]:
            if t.get(field) not in ids[target]: errors.append(f"{t['id']} references missing {field} {t.get(field)}")
        for x in t.get("blocked_by_task_ids",[]):
            if x not in ids["tasks"]: errors.append(f"{t['id']} references missing blocking task {x}")
    for d in decisions:
        for field,target in [("meeting_id","meetings"),("made_by_id","employees")]:
            if d.get(field) not in ids[target]: errors.append(f"{d['id']} references missing {field} {d.get(field)}")
        for x in d.get("affected_project_ids",[]):
            if x not in ids["projects"]: errors.append(f"{d['id']} references missing affected project {x}")
    for m in meetings:
        if not date_ok(m["date"]): errors.append(f"{m['id']} has invalid meeting date")
    for d in docs:
        if d["status"] not in STATUSES["documents"]: errors.append(f"{d['id']} has invalid document status {d['status']}")
    # A path check measures connected graph reachability, and scenario-level evidence checks its actual chain.
    reachable=set();
    if ids["projects"]:
        q=deque([next(iter(ids["projects"]))]); reachable.add(q[0])
        while q:
            for nxt in graph[q.popleft()]:
                if nxt not in reachable: reachable.add(nxt); q.append(nxt)
    connected=len(reachable)==len(all_ids)
    if not connected: warnings.append(f"Graph component from first project reaches {len(reachable)} of {len(all_ids)} entity nodes.")
    def has_edge(typ,src,dst): return any(x.get("type")==typ and x.get("source_id")==src and x.get("target_id")==dst for x in rel)
    scenario_pass=0
    for s in scenarios:
        ev=s.get("evidence",{}); pid=s.get("target_project_id"); dids=ev.get("decision_ids",[]); mids=ev.get("meeting_ids",[]); tids=ev.get("task_ids",[]); docids=ev.get("document_ids",[]); contact=ev.get("expert_contact_employee_id")
        missing=[]
        if pid not in ids["projects"]: missing.append(f"project {pid}")
        if not dids or any(x not in ids["decisions"] for x in dids): missing.append("decision evidence")
        if not mids or any(x not in ids["meetings"] for x in mids): missing.append("meeting evidence")
        if len(tids)<2 or any(x not in ids["tasks"] for x in tids): missing.append("task chain")
        if not docids or any(x not in ids["documents"] for x in docids): missing.append("document evidence")
        if contact not in ids["employees"]: missing.append("expert contact")
        if dids and not any(has_edge("PROJECT_BLOCKED_BY_DECISION",pid,d) for d in dids): missing.append("project-to-decision blocker relationship")
        if dids and not any(has_edge("DECISION_AFFECTS_PROJECT",d,pid) for d in dids): missing.append("decision-to-project relationship")
        if dids and not any(has_edge("MEETING_MADE_DECISION",m,d) for m in mids for d in dids): missing.append("meeting rationale link")
        if tids and not any(has_edge("PROJECT_HAS_TASK",pid,t) for t in tids): missing.append("project task link")
        if len(tids)>1 and not any(has_edge("TASK_BLOCKED_BY_TASK",tids[1],tids[0]) for _ in [0]): missing.append("task blocker chain")
        if docids and not any(x.get("type")=="DOCUMENT_MENTIONS_PROJECT" and x.get("source_id") in docids and x.get("target_id")==pid for x in rel): missing.append("document project mention")
        if contact and not any(x.get("type")=="EMPLOYEE_HAS_EXPERTISE" and x.get("source_id")==contact for x in rel): missing.append("contact expertise")
        for scenario_pid in ev.get("related_project_ids",[]):
            if scenario_pid not in ids["projects"]: missing.append(f"related project {scenario_pid}")
        # Validate scenario references against meeting/document source files and ensure a graph route spans 4+ edges.
        for mid in mids:
            mt=next((x for x in meetings if x["id"]==mid),None)
            if not mt or (dids and not any(d in mt["body"] for d in dids)): missing.append(f"meeting file lacks decision rationale for {mid}")
        for docid in docids:
            if not any(x["id"]==docid for x in docs): missing.append(f"missing document source for {docid}")
        if dids and mids:
            decision=next((x for x in decisions if x["id"]==dids[0]),None)
            maker=decision.get("made_by_id") if decision else None
            expertise=next((x.get("target_id") for x in rel if x.get("type")=="EMPLOYEE_HAS_EXPERTISE" and x.get("source_id")==maker),None)
            route=[pid,dids[0],maker,expertise]
            if any(not route[i] or route[i+1] not in graph.get(route[i],set()) for i in range(len(route)-1)): missing.append("3+ hop evidence path")
        if missing: errors.append(f"{s.get('id','?')} insufficient evidence: {', '.join(dict.fromkeys(missing))}")
        else: scenario_pass+=1
    if len(scenarios)<5: errors.append(f"Expected at least 5 investigation scenarios, found {len(scenarios)}")
    # Documents listed in the catalog must map to actual markdown with the same source ID.
    for d in docs:
        if not d.get("source_id") or d["source_id"] not in d["body"]: errors.append(f"{d['id']} source ID missing from markdown")
    print("NovaTech dataset validation")
    print("Records: "+", ".join(f"{k}={v}" for k,v in count_map.items())+f", scenarios={len(scenarios)}, relationships={len(rel)}")
    print(f"Relationship types: {len(edge_types)}/{len(REQUIRED)} required types present")
    print(f"Connected graph: {'yes' if connected else 'partial'} ({len(reachable)}/{len(all_ids)} entities reachable from first project)")
    print(f"Investigation scenarios with sufficient evidence: {scenario_pass}/{len(scenarios)}")
    for w in warnings: print(f"WARNING: {w}")
    for e in errors: print(f"ERROR: {e}")
    if errors: print(f"FAILED: {len(errors)} critical issue(s)"); return 1
    print("PASSED: no critical data quality issues found"); return 0

if __name__=="__main__": sys.exit(main())
