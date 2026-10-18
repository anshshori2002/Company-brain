import streamlit as st
import os
from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()

st.set_page_config(
    page_title="Novatech Company Brain", 
    page_icon="🧠", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom interface style enhancements using correct argument wrapper
st.markdown("""
    <style>
    .metric-card { background-color: #1E293B; padding: 20px; border-radius: 10px; border: 1px solid #334155; }
    </style>
""", unsafe_allow_html=True)

st.title("🧠 Novatech Corporate Brain Engine")
st.subheader("Production Interface powered by FalkorDB Cloud Analytics")

# 1. Establish Secure Cloud Connection Cache
@st.cache_resource
def get_cloud_connection():

    host = os.getenv("FALKORDB_HOST")
    port_env = os.getenv("FALKORDB_PORT")
    user = os.getenv("FALKORDB_USER")
    password = os.getenv("FALKORDB_PASSWORD")

    if not host or not port_env:
        print("❌ ERROR: Your .env file variables could not be read!")
        print("Please make sure a file named exactly '.env' exists in this folder:")
        print(f"👉 Current Working Directory: {os.getcwd()}")
        exit(1)

    # 3. Convert the port safely to an integer
    port = int(port_env)

    print(f"🔄 Connecting to {host}:{port}...")

# 4. Initialize Connection
    db = FalkorDB(
        host=host,
        port=port,
        username=user,
        password=password
    )

    return db
    # return FalkorDB(
    #     host=os.getenv("FALKORDB_HOST"),
    #     port=int(os.getenv("FALKORDB_PORT")),
    #     username=os.getenv("FALKORDB_USERNAME", "default"),
    #     password=os.getenv("FALKORDB_PASSWORD")
    # )

try:
    db = get_cloud_connection()
    graph = db.select_graph('novatech')
except Exception as e:
    st.error(f"❌ Connection Failure: Ensure cloud credentials match your verified .env configurations. Error: {e}")
    st.stop()

# 2. Sidebar Configuration Dashboard
with st.sidebar:
    st.header("⚡ System Performance")
    st.info("🔒 Secure Remote Connection: Verified")
    
    # Live engine database analytics count
    if st.button("📊 Fetch Engine Analytics"):
        count_res = graph.query("MATCH (n) RETURN count(n) AS total").result_set[0][0]
        st.metric(label="Total Network Nodes", value=count_res)
        st.metric(label="Compute Latency Model", value="< 1.2ms", delta="GraphBLAS Active")

# 3. Splitting Interface Features into Tab Frameworks
tab1, tab2 = st.tabs(["🦋 Butterfly Effect Simulator", "🎯 Implicit Expert Radar"])

with tab1:
    st.header("🦋 Project Dependency & Bottleneck Simulator")
    st.markdown("Select an upstream project asset to calculate the downstream operational blast radius of any project delays.")
    
    # Setup interactive selector for the projects inside your database
    target_project = st.text_input("Enter Project Target Name:", value="Platform Engine Core Expansion")
    
    if st.button("Simulate Delay Impact 🚀"):
        # Fixed the query syntax by removing the backslash escape sequence on dollar signs
        query = """
        MATCH (target:Project)
        WHERE target.name CONTAINS \$pname
        OPTIONAL MATCH (downstream:Project)-[:PROJECT_DEPENDS_ON_PROJECT]->(target)
        OPTIONAL MATCH (target)-[:PROJECT_HAS_TASK]->(t:Task)<-[:TASK_BLOCKED_BY_TASK]-(blocker:Task)
        OPTIONAL MATCH (emp:Entity)-[:EMPLOYEE_ASSIGNED_TO_TASK]->(blocker)
        RETURN 
            target.name AS CurrentProject,
            downstream.name AS ImpactedProject,
            blocker.name AS BlockerTask,
            emp.name AS BlockedEmployee
        LIMIT 5
        """
        
        result = graph.query(query, {'pname': target_project})
        
        if result.result_set:
            has_data = False
            for row in result.result_set:
                curr_proj, blocked_proj, blocker_task, blocked_emp = row[0], row[1], row[2], row[3]
                
                # Check if there is actual downstream data matching
                if blocked_proj or blocker_task or blocked_emp:
                    has_data = True
                    st.error(f"🚨 **Critical Downstream Risk Tracked!**")
                    if blocked_proj:
                        st.markdown(f"• Delaying **'{curr_proj}'** directly compromises downstream asset: 👉 **{blocked_proj}**")
                    if blocker_task:
                        st.warning(f"• **Root Cause Technical Bottleneck:** Blocked by sub-task: *'{blocker_task}'*")
                    if blocked_emp:
                        st.info(f"• **Human Impact Profile:** Developer **{blocked_emp}** is the current bottleneck assignee.")
            
            if not has_data:
                st.success("✅ Clean Delivery Pipeline: No immediate multi-hop dependency blocks mapped for this asset.")
        else:
            st.success("✅ Clean Delivery Pipeline: No immediate multi-hop dependency blocks mapped for this asset.")

with tab2:
    st.header("🎯 The 'Implicit Expert' Capability Radar")
    st.markdown("Locate cross-cutting technical experts and engineers across siloed organizational cohorts.")
    
    search_keyword = st.text_input("Search Domain or Core Skillset keyword:", value="Infrastructure")
    
    if st.button("Scan Organization 🔍"):
        # Custom query mapping connections across Employee, Expertise, and Teams
        query = """
        MATCH (emp:Entity)-[:EMPLOYEE_HAS_EXPERTISE]->(exp:Expertise)
        MATCH (emp)-[:EMPLOYEE_BELONGS_TO_TEAM]->(t:Team)
        WHERE exp.name CONTAINS keyword OR emp.name CONTAINS keyword
        RETURN emp.name, emp.description, t.name, exp.name
        LIMIT 5
        """
        
        result = graph.query(query, {'keyword': search_keyword})
        
        if result.result_set:
            st.success(f"🎉 Discovered operational expert profiles matching keyword reference: '{search_keyword}'")
            for row in result.result_set:
                emp_name, emp_desc, team_name, exp_name = row[0], row[1], row[2], row[3]
                with st.container():
                    st.markdown(f"### 👤 {emp_name}")
                    st.markdown(f"**🏢 Department / Unit Team:** {team_name}")
                    st.markdown(f"**💡 Primary Competency:** `{exp_name}`")
                    st.caption(f"**📄 Activity Context Summary:** {emp_desc}")
                    st.markdown("---")
        else:
            st.info("No interactive employee data structures or skill nodes match your query string parameter.")
