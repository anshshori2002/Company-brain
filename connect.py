import os
from dotenv import load_dotenv
from falkordb import FalkorDB

# 1. Explicitly load the environmental variables
load_dotenv()

# 2. Extract settings and print a warning if they are missing
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

graph = db.select_graph('novatech')
print("🌐 Successfully connected to the Corporate Brain on FalkorDB Cloud!")
