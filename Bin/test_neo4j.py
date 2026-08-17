from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    "bolt://127.0.0.1:7687",
    auth=("neo4j", "password")
)

driver.verify_connectivity()

print("Connexion Neo4j OK")

driver.close()