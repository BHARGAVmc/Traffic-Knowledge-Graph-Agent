import requests
from neo4j import GraphDatabase


# ============================================================
# Ollama Configuration
# ============================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"


# ============================================================
# Neo4j Configuration
# ============================================================

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password123"

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD)
)


# ============================================================
# Knowledge Graph Schema
# ============================================================

KG_SCHEMA = """

Nodes:

APDistrict
Properties:
- name

RoadSegment
Properties:
- segmentId
- linestring
- length_m

TrafficObservation
Properties:
- congestion_m
- timestamp

TrafficTime
Properties:
- timestamp


Relationships:

(APDistrict)-[:CONTAINS]->(RoadSegment)

(RoadSegment)-[:HAS_OBSERVATION]->(TrafficObservation)

(TrafficObservation)-[:AT_TIME]->(TrafficTime)

"""


# ============================================================
# Generate Cypher
# ============================================================

def generate_cypher(question):

    prompt = f"""
You are a Neo4j Knowledge Graph query agent.

Your job is to convert the user's natural-language question
into a valid Neo4j Cypher query.

Knowledge Graph schema:

{KG_SCHEMA}

STRICT RULES:

1. Use ONLY the labels defined in the schema.
2. Use ONLY the properties defined in the schema.
3. Use ONLY the relationships defined in the schema.
4. Never invent labels.
5. Never invent properties.
6. Never invent relationships.
7. Use valid Neo4j Cypher.
8. Always return useful data.
9. For questions asking for highest/lowest values, use ORDER BY.
10. For questions asking for a count, use count().
11. Generate ONLY Cypher.
12. Do NOT explain.
13. Do NOT use markdown.
14. Do NOT use code fences.

Examples:

Question:
How many districts are in the database?

Cypher:
MATCH (d:APDistrict)
RETURN count(d) AS district_count

Question:
How many road segments are in each district?

Cypher:
MATCH (d:APDistrict)-[:CONTAINS]->(r:RoadSegment)
RETURN d.name AS district, count(r) AS road_segments
ORDER BY road_segments DESC

Question:
Show the roads in Tirupati.

Cypher:
MATCH (d:APDistrict {{name: "Tirupati"}})-[:CONTAINS]->(r:RoadSegment)
RETURN r.segmentId, r.linestring, r.length_m

Question:
Show traffic observations for Tirupati.

Cypher:
MATCH (d:APDistrict {{name: "Tirupati"}})
      -[:CONTAINS]->(r:RoadSegment)
      -[:HAS_OBSERVATION]->(o:TrafficObservation)
RETURN r.segmentId, o.timestamp, o.congestion_m
ORDER BY o.timestamp

Question:
Which road has the highest congestion?

Cypher:
MATCH (r:RoadSegment)-[:HAS_OBSERVATION]->(o:TrafficObservation)
RETURN r.segmentId, o.congestion_m, o.timestamp
ORDER BY o.congestion_m DESC
LIMIT 1

User question:
{question}
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0
            }
        },
        timeout=120
    )

    response.raise_for_status()

    return response.json()["response"].strip()


# ============================================================
# Clean Cypher
# ============================================================

def clean_cypher(cypher):

    cypher = cypher.replace("```cypher", "")
    cypher = cypher.replace("```", "")

    cypher = cypher.replace("\\:", ":")
    cypher = cypher.replace("\\_", "_")

    return cypher.strip()


# ============================================================
# Execute Cypher
# ============================================================

def execute_cypher(cypher):

    with driver.session() as session:

        result = session.run(cypher)

        return [record.data() for record in result]


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    print("==============================================")
    print(" AP TRAFFIC KNOWLEDGE GRAPH AGENT")
    print(" Ollama + Qwen + Neo4j")
    print("==============================================")

    question = input("\nAsk a question:\n> ")

    print("\nGenerating Cypher using Qwen...\n")

    try:

        cypher = generate_cypher(question)

        cypher = clean_cypher(cypher)

        print("Generated Cypher:")
        print("----------------------------------------------")
        print(cypher)
        print("----------------------------------------------")

        print("\nExecuting query in Neo4j...\n")

        result = execute_cypher(cypher)

        print("Result:")
        print("----------------------------------------------")

        if result:

            for row in result:
                print(row)

        else:

            print("No results found.")

        print("----------------------------------------------")

    except Exception as e:

        print("\nError:")
        print(e)

    finally:

        driver.close()