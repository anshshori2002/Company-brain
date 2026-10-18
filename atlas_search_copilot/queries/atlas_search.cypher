MATCH (p:Project {id: $project_id})-[:PROJECT_BLOCKED_BY_DECISION]->(d:Decision)
OPTIONAL MATCH (d)-[:DECISION_MADE_BY_EMPLOYEE]->(owner:Employee)
OPTIONAL MATCH (meeting:Meeting)-[:MEETING_MADE_DECISION]->(d)
OPTIONAL MATCH (dependent:Project)-[:PROJECT_DEPENDS_ON_PROJECT]->(p)
OPTIONAL MATCH (p)-[:PROJECT_HAS_TASK]->(task:Task)
OPTIONAL MATCH (doc:Document)-[:DOCUMENT_MENTIONS_PROJECT]->(p)
RETURN p.id AS project_id, p.name AS project_name, p.status AS project_status,
       p.description AS project_description, p.blockers AS project_blockers,
       d.id AS decision_id, d.title AS decision_title,
       d.description AS decision_description, d.status AS decision_status,
       owner.id AS owner_id, owner.name AS owner_name, owner.title AS owner_title,
       owner.expertise AS owner_expertise,
       meeting.id AS meeting_id, meeting.title AS meeting_title,
       meeting.date AS meeting_date, meeting.text AS meeting_source,
       collect(DISTINCT CASE WHEN dependent IS NULL THEN null ELSE
         {id: dependent.id, name: dependent.name, status: dependent.status} END) AS dependent_projects,
       collect(DISTINCT CASE WHEN task IS NULL THEN null ELSE
         {id: task.id, title: task.title, status: task.status} END) AS tasks,
       collect(DISTINCT CASE WHEN doc IS NULL THEN null ELSE
         {id: doc.id, title: doc.title, status: doc.status, updated_at: doc.updated_at, text: doc.text} END) AS documents
