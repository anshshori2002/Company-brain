import streamlit as st
import os
import random
import ollama  # Import the local Ollama interface
from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()

st.set_page_config(
    page_title="Novatech CorpBrain Chatbot", 
    page_icon="🤖", 
    layout="centered"
)

# 1. Establish Secure Cloud Connection Cache
@st.cache_resource
def get_cloud_connection():
    host = os.getenv("FALKORDB_HOST")
    port_env = os.getenv("FALKORDB_PORT")
    user = os.getenv("FALKORDB_USER")
    password = os.getenv("FALKORDB_PASSWORD")

    if not host or not port_env:
        print("❌ ERROR: Your .env file variables could not be read!")
        exit(1)

    port = int(port_env)
    db = FalkorDB(host=host, port=port, username=user, password=password)
    return db

try:
    db = get_cloud_connection()
    graph = db.select_graph('novatech')
except Exception as e:
    st.error(f"❌ Connection Failure: {e}")
    st.stop()

# 2. Setup Persistent Conversational Memory State
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "👋 Hello! I am the **Novatech CorpBrain AI Agent**. I sit directly over our company's projects, task streams, expert networks, and internal decisions using Ollama to translate your questions into graph patterns. Ask me anything!"}
    ]

# 3. Sidebar: Smart Recommended & Unique Queries Console
with st.sidebar:
    st.title("💡 Smart Recommendations")
    
    recommended_queries = {
        #"🔍 Find Infrastructure Experts": "Who has 'Infrastructure' expertise in our company and what team do they belong to?",
        #"🦋 Simulate Dependency Risk": "What downstream projects or tasks will be impacted if our Platform Expansion project stalls?",
        "📊 Database Operational Health": "Show me a quick high-level summary of all corporate network items tracked inside our database engine."
    }
    
    clicked_prompt = None
    for label, query_text in recommended_queries.items():
        if st.button(label, use_container_width=True):
            clicked_prompt = query_text

# 4. Render Active Chat Conversation Streams
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. Core Text-to-Cypher Engine using Ollama
def generate_cypher_with_ollama(user_prompt):
    """Feeds the database schema context along with precise few-shot examples into Ollama."""
    
    # Updated with singular node labels, UPPERCASE relationships, and clear translation templates
    system_schema_context = """
    You are an expert Text-to-Cypher translator for FalkorDB.
    Your sole task is to turn user natural language questions into valid OpenCypher queries based on the EXACT schema layout below.
    
    DATABASE SCHEMA GRAPH KNOWLEDGE:
    - Labels (Strictly Case-Sensitive): Team, Task, Project, Meeting, Expertise, Entity, Employee, Document, Decision
    - Relationships (Strictly Case-Sensitive):
      (Employee)-[:EMPLOYEE_HAS_EXPERTISE]->(Expertise)
      (Project)-[:PROJECT_HAS_TASK]->(Task)
      (Employee)-[:EMPLOYEE_ASSIGNED_TO_TASK]->(Task)
      (Decision)-[:DECISION_AFFECTS_PROJECT]->(Project)
      (Decision)-[:DECISION_MADE_BY_EMPLOYEE]->(Employee)
      (Meeting)-[:MEETING_MADE_DECISION]->(Decision)
      (Document)-[:DOCUMENT_MENTIONS_PROJECT]->(Project)
      (Employee)-[:EMPLOYEE_BELONGS_TO_TEAM]->(Team)
      (Task)-[:TASK_BLOCKED_BY_TASK]->(Task)
      (Employee)-[:EMPLOYEE_OWNS_PROJECT]->(Project)
      (Decision)-[:PROJECT_BLOCKED_BY_DECISION]->(Project)
      (Project)-[:PROJECT_DEPENDS_ON_PROJECT]->(Project)

    CRITICAL COMPILATION INSTRUCTIONS:
    1. Respond ONLY with the executable OpenCypher string. Do not include markdown code block styling like ```cypher or ```.
    2. Do not write any conversational text, descriptions, or explanations.
    3. NEVER use multiple WHERE clauses in a single query path. Combine conditions into one single statement using 'AND' or 'OR'.
    4. Labels and Relationships are STRICTLY CASE-SENSITIVE. Use the exact casing provided above.
    5. Strings in WHERE clauses must be literal strings using single or double quotes.
    6. Always return clean properties (e.g., RETURN e.name, t.name) rather than whole nodes. Limit returns to 5.

    FEW-SHOT TRANSLATION EXAMPLES TO IMITATE:

    Example 1:
    User: Who has 'Infrastructure' expertise in our company and what team do they belong to?
    Cypher: MATCH (e:Employee)-[:EMPLOYEE_HAS_EXPERTISE]->(ex:Expertise) MATCH (e)-[:EMPLOYEE_BELONGS_TO_TEAM]->(t:Team) WHERE ex.name CONTAINS 'Infrastructure' RETURN e.name, t.name, ex.name LIMIT 5

    Example 2:
    User: Show me all tasks blocking our critical milestones that are owned by the infrastructure team.
    Cypher: MATCH (t1:Task)-[:TASK_BLOCKED_BY_TASK]->(t2:Task) MATCH (e:Employee)-[:EMPLOYEE_ASSIGNED_TO_TASK]->(t1) MATCH (e)-[:EMPLOYEE_BELONGS_TO_TEAM]->(team:Team) WHERE team.name CONTAINS 'Infrastructure' RETURN t1.name, t2.name, e.name LIMIT 5

    Example 3:
    User: List all decisions made by employee Jane Doe that impacted active client deliverables.
    Cypher: MATCH (d:Decision)-[:DECISION_MADE_BY_EMPLOYEE]->(e:Employee) MATCH (d)-[:DECISION_AFFECTS_PROJECT]->(p:Project) WHERE e.name = 'Jane Doe' RETURN d.name, p.name LIMIT 5

    Example 4:
    User: What downstream projects or tasks will be impacted if our Platform Expansion project stalls?
    Cypher: MATCH (p1:Project)-[:PROJECT_DEPENDS_ON_PROJECT]->(p2:Project) WHERE p1.name CONTAINS 'Platform Expansion' RETURN p2.name LIMIT 5
    """

    try:
        # Call local Ollama model (using llama3.2 as specified)
        response = ollama.chat(
            model='llama3.2',
            messages=[
                {'role': 'system', 'content': system_schema_context},
                {'role': 'user', 'content': f"Translate this question into a single raw Cypher query string: {user_prompt}"}
            ]
        )
        
        # Strip trailing characters, white space, or markdown wrappers
        cypher_query = response['message']['content'].strip()
        cypher_query = cypher_query.replace("```cypher", "").replace("```", "").strip()
        return cypher_query
    except Exception as e:
        st.error(f"Ollama Connection Error: {e}")
        return None


def generate_narrative_explanation(user_prompt, raw_graph_results):
    """Passes raw graph data rows back to Ollama to generate a natural conversational summary."""
    narrative_prompt = f"""
    You are the Novatech CorpBrain AI assistant. 
    A user asked the following question: "{user_prompt}"
    
    The database graph search returned the following raw data records:
    {str(raw_graph_results)}
    
    INSTRUCTIONS:
    1. Write a direct, clear, and professional explanation summarizing these data points in plain English.
    2. Explain what the data means in the context of the user's question (e.g., if the user asked about bottlenecks and the data shows projects, explain that these projects represent active blockers or dependencies).
    3. Keep the summary punchy, accessible, and under 3-4 sentences. Do not mention database terms like 'nodes', 'rows', 'result_set', or 'Cypher'.
    """
    
    try:
        response = ollama.chat(
            model='llama3.2',
            messages=[
                {'role': 'system', 'content': 'You are a professional corporate operations analyst.'},
                {'role': 'user', 'content': narrative_prompt}
            ]
        )
        return response['message']['content'].strip()
    except Exception as e:
        return f"⚠️ Could not compile summary: {e}"

def process_agent_response(user_input):
    """Converts user query using Ollama, queries FalkorDB, and returns the response with an AI narrative."""
    
    if "summary" in user_input.lower() and "database" in user_input.lower():
        count_res = graph.query("MATCH (n) RETURN count(n) AS total").result_set
        return f"📊 **CorpBrain Operational Analytics:** Currently monitoring **{count_res[0][0]}** asset nodes inside the live FalkorDB cluster environment."

    st.info("🤖 *Ollama is generating graph path queries...*")
    
    # 1. Ask Ollama to translate the prompt into an OpenCypher query
    generated_query = generate_cypher_with_ollama(user_input)
    
    if not generated_query:
        return "❌ Failed to generate structural graph query path."
    
    with st.status("🔍 Inspecting Compiled Cypher Expression...", expanded=False):
        st.code(generated_query, language="cypher")

    # 2. Run the generated query against FalkorDB
    try:
        result = graph.query(generated_query)
        
        if not result.result_set:
            return "ℹ️ Query successfully executed, but no matching entities or relational links were discovered in the database matrix mapping."
        
        # 3. Format raw output data rows safely
        response_text = "🎯 **Graph Extraction Matrix Results:**\n\n"
        for row in result.result_set:
            row_items = [f"`{str(item)}`" for item in row]
            response_text += f"• {' ──> '.join(row_items)}\n"
            
        response_text += "\n"
        
        # 4. Generate and append the new AI structural narrative overview
        st.info("🧠 *Ollama is generating narrative context...*")
        ai_explanation = generate_narrative_explanation(user_input, result.result_set)
        
        response_text += f"📝 **Operational Summary:**\n{ai_explanation}"
        return response_text

    except Exception as cypher_error:
        return (f"⚠️ **Cypher Engine Execution Refusal:**\n\n"
                f"The Ollama model generated an incorrect syntax statement for this schema layout.\n"
                f"*Error:* `{cypher_error}`\n\n"
                f"*Generated Query:* \n```cypher\n{generated_query}\n```")

# 6. Monitor Chat Inputs and Append Flows
user_query = st.chat_input("Ask CorpBrain about teams, tasks, decisions, or roadblocks...")

if clicked_prompt:
    user_query = clicked_prompt

if user_query:
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        response = process_agent_response(user_query)
        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
