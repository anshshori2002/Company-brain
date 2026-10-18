import os
from dotenv import load_dotenv
from falkordb import FalkorDB

# 1. Load your working cloud credentials from your secure .env file
load_dotenv()

# 2. Establish connection to your production cloud endpoint
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

# Select the target graph container where your corporate data sits
graph = db.select_graph('novatech')
print("🌐 Connected to FalkorDB Cloud. Scanning database data models...\n")

def check_node_labels_and_counts():
    """Query 1: Discovers all unique node categories and exactly how many exist."""
    print("📊 [SCHEMA EXPLORATION] Unique Node Types and Counts:")
    
    query = """
    MATCH (n) 
    RETURN labels(n)[0] AS NodeType, count(n) AS EntityCount
    """
    result = graph.query(query)
    
    for row in result.result_set:
        print(f"   • Label Category: {row[0]} | Count: {row[1]}")
    print("-" * 65)

def preview_nodes_with_properties():
    """Query 2: Pulls up a raw structural text sample of actual nodes with their keys."""
    print("🔍 [ENTITY INSPECTION] Sample Nodes & Embedded Attributes:")
    
    query = """
    MATCH (n) 
    RETURN labels(n)[0] AS Label, n AS RawNode
    LIMIT 5
    """
    result = graph.query(query)
    
    for row in result.result_set:
        label = row[0]
        # FalkorDB entity nodes contain an internal .properties dictionary mapping
        node_obj = row[1]
        properties = node_obj.properties if hasattr(node_obj, 'properties') else {}
        print(f"   • [{label}] Properties: {properties}")
    print("-" * 65)

def mapping_relationship_edges():
    """Query 3: Discovers how different categories are mapped and wired together."""
    print("🔗 [NETWORK RELATIONSHIPS] Structural Edge Pathways Mapped:")
    
    query = """
    MATCH (a)-[r]->(b) 
    RETURN DISTINCT labels(a)[0] AS Source, type(r) AS RelationshipType, labels(b)[0] AS Target
    LIMIT 10
    """
    result = graph.query(query)
    
    for row in result.result_set:
        print(f"   • ({row[0]}) -[:{row[1]}]-> ({row[2]})")
    print("=" * 65)

if __name__ == "__main__":
    try:
        check_node_labels_and_counts()
        preview_nodes_with_properties()
        mapping_relationship_edges()
    except Exception as e:
        print(f"❌ Diagnostic Query Failed: {e}")
