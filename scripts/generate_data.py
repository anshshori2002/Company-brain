#!/usr/bin/env python3
"""Generate a reproducible, evidence-rich fictional NovaTech knowledge graph."""
from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = datetime(2025, 1, 6, 9, 0, tzinfo=timezone.utc)
TEAMS = [
    ("TEAM001", "Platform Engineering", "Builds shared infrastructure and developer tooling."),
    ("TEAM002", "Applied AI", "Develops model services, evaluation, and retrieval systems."),
    ("TEAM003", "Product Experience", "Owns customer workflows and product design."),
    ("TEAM004", "Security and Trust", "Owns security controls, privacy, and governance."),
    ("TEAM005", "Data Operations", "Owns data pipelines, analytics, and reliability."),
]
PEOPLE = [
    ("Avery", "Quill", "Platform Engineering", "distributed systems; Kubernetes; observability"),
    ("Mira", "Solace", "Applied AI", "retrieval augmented generation; evaluation; Python"),
    ("Jonah", "Venn", "Product Experience", "product strategy; workflow design; accessibility"),
    ("Talia", "Wren", "Security and Trust", "privacy engineering; threat modeling; identity"),
    ("Ravi", "Kestrel", "Data Operations", "data lineage; streaming; SQL"),
    ("Niko", "Vale", "Platform Engineering", "API design; service reliability; Go"),
    ("Sana", "Pike", "Applied AI", "model serving; prompt evaluation; Python"),
    ("Elio", "Morrow", "Product Experience", "design systems; user research; prototyping"),
    ("Lena", "Ashby", "Security and Trust", "compliance; access control; incident response"),
    ("Omar", "Briar", "Data Operations", "warehouse design; ETL; data quality"),
    ("Cleo", "North", "Platform Engineering", "networking; Terraform; cloud cost"),
    ("Ishan", "Rowe", "Applied AI", "vector search; ranking; information retrieval"),
    ("Freya", "Mills", "Product Experience", "experimentation; product analytics; UX writing"),
    ("Zane", "Hart", "Security and Trust", "cryptography; key management; secure SDLC"),
    ("Ada", "Lark", "Data Operations", "event systems; lineage; Python"),
    ("Theo", "Fenn", "Platform Engineering", "CI/CD; container security; SRE"),
    ("Imani", "Reed", "Applied AI", "multimodal models; evaluation; retrieval"),
    ("Pavel", "Dune", "Product Experience", "billing; integrations; customer onboarding"),
    ("Nora", "Sable", "Security and Trust", "data governance; privacy reviews; policy"),
    ("Kai", "Ember", "Data Operations", "stream processing; monitoring; analytics"),
]
PROJECT_SEEDS = [
    ("PRJ001", "Atlas Search", "Applied AI", "delayed", "2025-06-30T17:00:00Z", "Tenant isolation gate blocks the retrieval pilot."),
    ("PRJ002", "Beacon Billing", "Product Experience", "at_risk", "2025-07-18T17:00:00Z", "Usage events are waiting on the Atlas schema contract."),
    ("PRJ003", "Cinder Identity", "Security and Trust", "delayed", "2025-07-04T17:00:00Z", "Key rotation approval requires an auditable recovery path."),
    ("PRJ004", "Drift Data Mesh", "Data Operations", "delayed", "2025-07-11T17:00:00Z", "Lineage export is blocked by the identity event format."),
    ("PRJ005", "Echo Console", "Product Experience", "at_risk", "2025-07-25T17:00:00Z", "Console launch depends on approved security status signals."),
    ("PRJ006", "Fjord Runtime", "Platform Engineering", "on_track", "2025-08-08T17:00:00Z", "Shared runtime upgrade is progressing in staged environments."),
    ("PRJ007", "Grove Assist", "Applied AI", "on_track", "2025-08-15T17:00:00Z", "Internal assistant quality review is underway."),
    ("PRJ008", "Halo Audit", "Security and Trust", "at_risk", "2025-08-22T17:00:00Z", "Evidence export depends on the data mesh lineage endpoint."),
    ("PRJ009", "Ion Connect", "Platform Engineering", "on_track", "2025-09-05T17:00:00Z", "Partner sandbox integration is in implementation."),
    ("PRJ010", "Juniper Metrics", "Data Operations", "on_track", "2025-09-12T17:00:00Z", "Operational metrics consolidation is in discovery."),
]
SCENARIO_SEEDS = [
    {"id":"SCN001", "project":"PRJ001", "question":"Why is Atlas Search delayed, which decision caused the blocker, who made it, and which other projects are affected?", "decision":"DEC001", "meeting":"MTG001", "tasks":["TASK001","TASK002"], "docs":["DOC001","DOC002"], "contact":"EMP004", "projects":["PRJ002","PRJ005"]},
    {"id":"SCN002", "project":"PRJ003", "question":"Why is Cinder Identity delayed, what recovery control is missing, and how does it affect Drift Data Mesh?", "decision":"DEC003", "meeting":"MTG003", "tasks":["TASK005","TASK006"], "docs":["DOC003","DOC004"], "contact":"EMP014", "projects":["PRJ004","PRJ008"]},
    {"id":"SCN003", "project":"PRJ004", "question":"Which upstream identity event prevents Drift lineage export, who can resolve it, and what evidence explains the dependency?", "decision":"DEC004", "meeting":"MTG004", "tasks":["TASK007","TASK008"], "docs":["DOC004","DOC005"], "contact":"EMP005", "projects":["PRJ008"]},
    {"id":"SCN004", "project":"PRJ005", "question":"Why is Echo Console at risk, which security decision controls its status display, and who owns the relevant expertise?", "decision":"DEC005", "meeting":"MTG005", "tasks":["TASK009","TASK010"], "docs":["DOC006","DOC007"], "contact":"EMP009", "projects":["PRJ001"]},
    {"id":"SCN005", "project":"PRJ008", "question":"Why is Halo Audit at risk, which dependency is upstream, and what approved policy supersedes the older guidance?", "decision":"DEC008", "meeting":"MTG008", "tasks":["TASK015","TASK016"], "docs":["DOC008","DOC009"], "contact":"EMP019", "projects":["PRJ004"]},
]

def stamp(day: int, hour: int = 9) -> str:
    return (BASE + timedelta(days=day, hours=hour-9)).isoformat(timespec="seconds").replace("+00:00", "Z")

def write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    ap.add_argument("--seed", type=int, default=20251016)
    ap.add_argument("--employees", type=int, default=20)
    ap.add_argument("--teams", type=int, default=5)
    ap.add_argument("--projects", type=int, default=10)
    ap.add_argument("--meetings", type=int, default=30)
    ap.add_argument("--decisions", type=int, default=30)
    ap.add_argument("--tasks", type=int, default=50)
    ap.add_argument("--documents", type=int, default=15)
    args = ap.parse_args()
    counts = {k: getattr(args, k) for k in ("employees","teams","projects","meetings","decisions","tasks","documents")}
    if any(v < 1 for v in counts.values()) or counts["employees"] < 5 or counts["projects"] < 5 or counts["meetings"] < 8 or counts["decisions"] < 8 or counts["tasks"] < 30 or counts["documents"] < 9 or counts["teams"] < 5:
        ap.error("Counts must be positive; preserving the five evidence scenarios requires at least 5 employees, 5 teams, 5 projects, 8 meetings, 8 decisions, 30 tasks, and 9 documents.")
    rng = random.Random(args.seed)
    out = args.output_dir.resolve()
    (out / "meetings").mkdir(parents=True, exist_ok=True)
    (out / "documents").mkdir(parents=True, exist_ok=True)

    teams = [{"id":tid,"name":name,"description":desc,"created_at":stamp(0)} for tid,name,desc in TEAMS[:counts["teams"]]]
    while len(teams) < counts["teams"]:
        n=len(teams)+1; teams.append({"id":f"TEAM{n:03d}","name":f"NovaTech Research {n}","description":"A fictional cross-functional research group.","created_at":stamp(0)})
    write_json(out/"teams.json", teams)
    employees=[]
    with (out/"employees.csv").open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=["id","name","title","team_id","expertise","created_at","updated_at"]); w.writeheader()
        for i in range(counts["employees"]):
            if i < len(PEOPLE):
                first,last,team_name,expertise=PEOPLE[i]
            else:
                first,last=f"Rin{i+1}",f"Vale{i+1}"; team_name=teams[i%len(teams)]["name"]; expertise="systems design; documentation; incident analysis"
            team=next((t for t in teams if t["name"]==team_name), teams[i%len(teams)])
            e={"id":f"EMP{i+1:03d}","name":f"{first} {last}","title":["Staff Engineer","Product Lead","Senior Engineer","Security Analyst","Data Engineer"][i%5],"team_id":team["id"],"expertise":[s.strip() for s in expertise.split(";")],"created_at":stamp(0),"updated_at":stamp(20)}
            employees.append(e); w.writerow({**e,"expertise":"; ".join(e["expertise"])})

    # The first ten projects and first five scenarios are a stable, interconnected story.
    projects=[]
    for i in range(counts["projects"]):
        if i < len(PROJECT_SEEDS):
            pid,name,team_name,status,due,risk=PROJECT_SEEDS[i]
        else:
            pid=f"PRJ{i+1:03d}"; name=f"Nova Initiative {i+1}"; team_name=teams[i%len(teams)]["name"]; status="on_track"; due=stamp(240); risk="No active risk recorded."
        team=next((t for t in teams if t["name"]==team_name),teams[i%len(teams)])
        owner=employees[(i*3+1)%len(employees)] if i < len(PROJECT_SEEDS) else employees[rng.randrange(len(employees))]
        history=[{"status":"on_track","changed_at":stamp(i),"reason":"Project kickoff and initial plan approved."}]
        if status!="on_track": history.append({"status":status,"changed_at":stamp(150+i),"reason":risk})
        projects.append({"id":pid,"name":name,"description":f"{name} delivers a fictional NovaTech capability. {risk}","team_id":team["id"],"owner_id":owner["id"],"status":status,"status_history":history,"deadline":due,"blockers":[risk] if status in ("delayed","at_risk") else [],"risks":[risk] if status in ("delayed","at_risk") else [],"created_at":stamp(i),"updated_at":stamp(150+i)})
    write_json(out/"projects.json", projects)

    meetings=[]; decisions=[]; tasks=[]; docs=[]; rel=[]
    def edge(kind, source, target, **extra): rel.append({"type":kind,"source_id":source,"target_id":target,**extra})
    for e in employees:
        edge("EMPLOYEE_BELONGS_TO_TEAM",e["id"],e["team_id"])
        for exp in e["expertise"]: edge("EMPLOYEE_HAS_EXPERTISE",e["id"],"pending", expertise=exp)
    for p in projects: edge("EMPLOYEE_OWNS_PROJECT",p["owner_id"],p["id"])
    project_ids=[p["id"] for p in projects]
    dependencies={"PRJ002":"PRJ001","PRJ004":"PRJ003","PRJ005":"PRJ001","PRJ008":"PRJ004"}
    for a,b in dependencies.items():
        if a in project_ids and b in project_ids: edge("PROJECT_DEPENDS_ON_PROJECT",a,b,reason="Upstream contract or evidence dependency")

    # Five tightly evidenced incident chains; each traverses project -> task -> blocker -> decision -> meeting/person.
    task_specs=[
        ("Atlas tenant-filter integration","PRJ001","blocked","DEC001","EMP002"),("Atlas isolation review","PRJ001","blocked","DEC001","EMP004"),
        ("Billing usage schema mapping","PRJ002","blocked","DEC002","EMP010"),("Billing event contract test","PRJ002","blocked","DEC002","EMP015"),
        ("Identity recovery runbook","PRJ003","blocked","DEC003","EMP014"),("Identity key-rotation rehearsal","PRJ003","blocked","DEC003","EMP009"),
        ("Identity event schema v2","PRJ004","blocked","DEC004","EMP005"),("Lineage export adapter","PRJ004","blocked","DEC004","EMP015"),
        ("Security status API","PRJ005","blocked","DEC005","EMP009"),("Console status explanation UI","PRJ005","blocked","DEC005","EMP003"),
        ("Runtime canary rollout","PRJ006","in_progress",None,"EMP006"),("Runtime rollback automation","PRJ006","in_progress",None,"EMP016"),
        ("Assistant evaluation set","PRJ007","in_progress",None,"EMP007"),("Assistant retrieval benchmark","PRJ007","in_progress",None,"EMP012"),
        ("Audit lineage evidence adapter","PRJ008","blocked","DEC008","EMP019"),("Audit export retention review","PRJ008","in_progress",None,"EMP014"),
        ("Partner sandbox provisioning","PRJ009","in_progress",None,"EMP011"),("Partner token exchange test","PRJ009","in_progress",None,"EMP014"),
        ("Metrics event inventory","PRJ010","in_progress",None,"EMP020"),("Metrics dashboard prototype","PRJ010","in_progress",None,"EMP013"),
    ]
    # 30 decisions and meetings; the initial eight decisions are scenario drivers.
    decision_text=[
        ("DEC001","Require tenant-scoped vector indexes before Atlas pilot","rejected","PRJ001","MTG001","EMP004","An isolation review found cross-tenant retrieval possible in the shared index. The pilot is held until per-tenant filters are enforced and tested."),
        ("DEC002","Freeze billing usage event fields until Atlas contract is stable","active","PRJ002","MTG002","EMP010","Billing cannot safely map usage without the canonical tenant and query identifiers from Atlas."),
        ("DEC003","Require dual-control recovery evidence before rotating identity keys","active","PRJ003","MTG003","EMP014","The first rehearsal had no independent recovery custodian. Rotation is held until a second approver and rollback evidence are recorded."),
        ("DEC004","Adopt identity event schema v2 with immutable subject IDs","active","PRJ004","MTG004","EMP005","Schema v1 drops the immutable subject ID required to join audit lineage. Data Operations cannot publish the export until v2 is emitted."),
        ("DEC005","Expose only approved security posture states in Echo Console","active","PRJ005","MTG005","EMP009","Raw control results reveal internal details. Echo must consume the reviewed status API, which depends on Atlas tenant isolation."),
        ("DEC006","Use staged canaries for Fjord runtime rollout","approved","PRJ006","MTG006","EMP006","A staged rollout limits blast radius while keeping the runtime migration reversible."),
        ("DEC007","Evaluate Grove Assist with a reviewed internal query set","approved","PRJ007","MTG007","EMP007","The first test set contained unapproved customer-like examples. The reviewed set provides repeatable coverage."),
        ("DEC008","Retain lineage export evidence for 180 days","approved","PRJ008","MTG008","EMP019","Audit export retention is approved, but the export remains blocked until Drift publishes lineage with the v2 identity subject."),
    ]
    for i in range(counts["meetings"]):
        mid=f"MTG{i+1:03d}"; day=10+i*5
        meetings.append({"id":mid,"title":f"NovaTech Weekly Delivery Review {i+1:02d}","date":stamp(day),"attendee_ids":[employees[(i+j*3)%len(employees)]["id"] for j in range(4)],"decision_ids":[],"source_id":f"MEETING-{mid}","status":"final","created_at":stamp(day),"updated_at":stamp(day+1)})
    for i in range(counts["decisions"]):
        if i<len(decision_text):
            did,title,status,pid,mid,maker,why=decision_text[i]
        else:
            did=f"DEC{i+1:03d}"; pid=project_ids[i%len(project_ids)]; mid=f"MTG{i+1:03d}" if i<counts["meetings"] else "MTG001"; maker=employees[(i*2)%len(employees)]["id"]
            title=f"Confirm delivery approach {i+1}"; status="approved"; why=f"The team selected a reversible implementation approach for {next(p['name'] for p in projects if p['id']==pid)}."
        if mid not in {m["id"] for m in meetings}: mid="MTG001"
        if pid not in project_ids: pid=project_ids[i%len(project_ids)]
        if maker not in {e["id"] for e in employees}: maker=employees[i%len(employees)]["id"]
        d={"id":did,"title":title,"description":why,"status":status,"meeting_id":mid,"made_by_id":maker,"affected_project_ids":[pid],"created_at":stamp(10+i*5),"updated_at":stamp(20+i*5)}
        decisions.append(d); meetings[int(mid[3:])-1]["decision_ids"].append(did)
        edge("MEETING_MADE_DECISION",mid,did); edge("DECISION_AFFECTS_PROJECT",did,pid); edge("DECISION_MADE_BY_EMPLOYEE",did,maker)
        if i in (0,2,3,4,7): edge("PROJECT_BLOCKED_BY_DECISION",pid,did,reason="Decision status gate described in the linked meeting")
    # Markdown meeting notes carry rationale, dissent, and the evidence trail.
    for m in meetings:
        ds=[d for d in decisions if d["id"] in m["decision_ids"]]
        content=[f"# {m['title']}","",f"- Meeting ID: {m['id']}",f"- Date: {m['date']}",f"- Status: {m['status']}",f"- Attendees: {', '.join(m['attendee_ids'])}","", "## Discussion", "NovaTech reviewed delivery progress, dependencies, and operational risks. Participants compared current evidence with earlier guidance and recorded the rationale below.",""]
        for d in ds:
            project=next(p for p in projects if p["id"] in d["affected_project_ids"])
            content += [f"## Decision {d['id']}: {d['title']}",d["description"],f"- Status: {d['status']}",f"- Affects: {project['id']} ({project['name']})",f"- Made by: {d['made_by_id']}",""]
        if not ds: content += ["## Notes","No formal decision was recorded. The review confirmed owners and next actions; risks remain tracked in the project register.",""]
        (out/"meetings"/f"meeting_{int(m['id'][3:]):03d}.md").write_text("\n".join(content),encoding="utf-8")

    # Task inventory, with explicit blocker chains in the first 20 curated tasks.
    for i in range(counts["tasks"]):
        if i<len(task_specs): name,pid,status,decision,assignee=task_specs[i]
        else:
            pid=project_ids[(i-20)%len(project_ids)]; name=f"{next(p['name'] for p in projects if p['id']==pid)} delivery task {i+1:02d}"; status="todo" if i%3 else "in_progress"; decision=None; assignee=employees[rng.randrange(len(employees))]["id"]
        tasks.append({"id":f"TASK{i+1:03d}","title":name,"description":f"Complete and document {name.lower()} for {pid}.","project_id":pid,"assignee_id":assignee if assignee in {e['id'] for e in employees} else employees[i%len(employees)]["id"],"status":status,"priority":"high" if status=="blocked" else "normal","due_date":stamp(70+i),"blocked_by_task_ids":[],"created_at":stamp(i),"updated_at":stamp(160+i),"source_ids":[f"MEETING-MTG{min(i//2+1,counts['meetings']):03d}"]})
        edge("PROJECT_HAS_TASK",pid,tasks[-1]["id"]); edge("EMPLOYEE_ASSIGNED_TO_TASK",tasks[-1]["assignee_id"],tasks[-1]["id"])
    # Block each scenario's second task on its first task, then connect downstream work across projects.
    for first,second in [(1,2),(5,6),(7,8),(9,10),(15,16),(29,30)]:
        if first<=len(tasks) and second<=len(tasks):
            tasks[second-1]["blocked_by_task_ids"].append(tasks[first-1]["id"]); edge("TASK_BLOCKED_BY_TASK",tasks[second-1]["id"],tasks[first-1]["id"],reason="Upstream task must complete first")
    # More cross-project task dependencies mirror the project dependency graph.
    for downstream,upstream in [(3,1),(7,5),(9,1),(15,7)]:
        if downstream<=len(tasks) and upstream<=len(tasks):
            tasks[downstream-1]["blocked_by_task_ids"].append(tasks[upstream-1]["id"]); edge("TASK_BLOCKED_BY_TASK",tasks[downstream-1]["id"],tasks[upstream-1]["id"],reason="Cross-project contract dependency")

    doc_specs=[
        ("NovaTech Tenant Isolation Standard","current","Current policy requires tenant-scoped indexes and reviewed isolation tests.","PRJ001 PRJ002 PRJ005"),
        ("Atlas Pilot Checklist","superseded","Older checklist allowed a shared index during internal pilots; this guidance was superseded after the isolation review.","PRJ001"),
        ("Identity Key Recovery Runbook","current","Key rotation requires dual control, a tested recovery custodian, and rollback evidence.","PRJ003 PRJ005"),
        ("Identity Event Contract v2","current","Schema v2 preserves immutable subject IDs required by lineage and audit exports.","PRJ003 PRJ004 PRJ008"),
        ("Data Lineage Export Interface","current","Drift publishes lineage only after receiving identity schema v2 events.","PRJ004 PRJ008"),
        ("Security Posture API Guide","current","Only reviewed posture states may be exposed to product surfaces.","PRJ001 PRJ005"),
        ("Echo Console Release Notes","draft","The initial draft assumed the console could display raw control results; security review replaced that plan.","PRJ005"),
        ("Audit Evidence Retention Policy","current","Approved audit evidence retention period is 180 days; evidence must be traceable to source events.","PRJ004 PRJ008"),
        ("Legacy Audit Export Notes","superseded","Earlier notes proposed 30-day retention and assumed schema v1; superseded by the approved retention policy and v2 contract.","PRJ004 PRJ008"),
        ("Fjord Runtime Rollout Guide","current","Canary and rollback stages for the runtime migration.","PRJ006"),
        ("Grove Assist Evaluation Protocol","current","Use the reviewed internal query set and record retrieval quality measures.","PRJ007"),
        ("Partner Sandbox Security Checklist","current","Sandbox credentials are short lived and isolated to test tenants.","PRJ009"),
        ("NovaTech Data Classification Guide","current","Defines fictional internal labels and handling requirements.","PRJ003 PRJ008"),
        ("Service Incident Review Template","current","Captures timeline, impact, decision links, owners, and follow-up tasks.","PRJ001 PRJ003 PRJ004"),
        ("Metrics Event Naming Guide","current","Standard event names and ownership for operations dashboards.","PRJ002 PRJ010"),
    ]
    for i in range(counts["documents"]):
        if i<len(doc_specs): title,status,body,mentions=doc_specs[i]
        else: title=f"NovaTech Engineering Note {i+1:02d}"; status="current"; pid=project_ids[(i-15)%len(project_ids)]; body=f"Implementation notes and owners for {pid}."; mentions=pid
        docid=f"DOC{i+1:03d}"; pids=mentions.split(); source_id=f"DOCUMENT-{docid}"
        d={"id":docid,"title":title,"status":status,"source_id":source_id,"path":f"documents/policy_{i+1:03d}.md","mentioned_project_ids":pids,"created_at":stamp(i*4),"updated_at":stamp(180+i)}; docs.append(d)
        for pid in pids:
            if pid in project_ids: edge("DOCUMENT_MENTIONS_PROJECT",docid,pid)
        (out/"documents"/f"policy_{i+1:03d}.md").write_text(f"# {title}\n\n- Document ID: {docid}\n- Source ID: {source_id}\n- Status: {status}\n- Updated: {d['updated_at']}\n\n{body}\n\nThis fictional NovaTech document is evidence for the project references listed in the structured catalog. Use status and update time to resolve conflicting guidance.\n",encoding="utf-8")

    # Add evidence relationships for expertise targets with collision-free, deterministic IDs.
    expertise_values=sorted({x for e in employees for x in e["expertise"]})
    exp_ids={x:f"EXP{i+1:03d}" for i,x in enumerate(expertise_values)}
    for r in rel:
        if r["type"]=="EMPLOYEE_HAS_EXPERTISE": r["target_id"]=exp_ids[r["expertise"]]
    scenarios=[]
    for s in SCENARIO_SEEDS:
        if not all(x in project_ids for x in [s["project"],*s["projects"]]) or not all(int(x[4:])<=len(tasks) for x in s["tasks"]): continue
        scenarios.append({"id":s["id"],"question":s["question"],"target_project_id":s["project"],"evidence":{"decision_ids":[s["decision"]],"meeting_ids":[s["meeting"]],"task_ids":s["tasks"],"document_ids":s["docs"],"related_project_ids":s["projects"],"expert_contact_employee_id":s["contact"]},"answer_path":["PROJECT_BLOCKED_BY_DECISION","DECISION_MADE_BY_EMPLOYEE","EMPLOYEE_HAS_EXPERTISE","MEETING_MADE_DECISION","PROJECT_DEPENDS_ON_PROJECT"],"answer_guidance":"Use the linked meeting rationale and current documents; treat superseded or draft guidance as historical context."})
    # ensure all relationship endpoints resolve; expertise IDs are declared as nodes in manifest.
    write_json(out/"tasks.json",tasks); write_json(out/"decisions.json",decisions); write_json(out/"scenarios.json",scenarios); write_json(out/"relationships.json",rel)
    manifest={"company":{"name":"NovaTech","description":"A wholly fictional technology company created for graph reasoning demonstrations."},"generated_at":stamp(200),"seed":args.seed,"counts":counts,"entity_files":{"employees":"employees.csv","teams":"teams.json","projects":"projects.json","tasks":"tasks.json","decisions":"decisions.json","meetings":"meetings/meeting_NNN.md","documents":"documents/policy_NNN.md","scenarios":"scenarios.json","relationships":"relationships.json"},"expertise_nodes":[{"id":exp_ids[x],"name":x} for x in expertise_values],"relationship_types":sorted({r["type"] for r in rel}),"status_values":{"projects":["on_track","at_risk","delayed","completed"],"tasks":["todo","in_progress","blocked","done"],"decisions":["approved","active","rejected","superseded"],"documents":["current","draft","superseded"]},"schema_version":"1.0"}
    write_json(out/"manifest.json",manifest)
    print(f"Generated NovaTech dataset in {out}")
    print("Counts: "+", ".join(f"{k}={v}" for k,v in counts.items()))

if __name__=="__main__": main()
