"""
title: AP Traffic Knowledge Graph
description: Query the Andhra Pradesh traffic Knowledge Graph stored in Neo4j.
"""

import requests
from neo4j import GraphDatabase


class Tools:

    def __init__(self):
        self.ollama_url = "http://host.docker.internal:11434/api/generate"
        self.model = "qwen2.5:3b"

        self.neo4j_uri = "bolt://host.docker.internal:7687"
        self.neo4j_user = "neo4j"
        self.neo4j_password = "password123"

        self.driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(
                self.neo4j_user,
                self.neo4j_password
            )
        )

    def query_ap_knowledge_graph(
        self,
        question: str
    ) -> str:
        """
        Ask a natural-language question about the AP Traffic Knowledge Graph.
        """

        schema = """
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

        prompt = f"""
You are a Neo4j Knowledge Graph query agent.

Generate a valid Cypher query for the user's question.

Knowledge Graph schema:

{schema}

Rules:

1. Use ONLY the labels in the schema.
2. Use ONLY the properties in the schema.
3. Use ONLY the relationships in the schema.
4. Never invent labels.
5. Never invent properties.
6. Never invent relationships.
7. Always return useful data.
8. Use count() for counting questions.
9. Use ORDER BY for highest or lowest questions.
10. Generate ONLY Cypher.
11. Do not explain.
12. Do not use markdown.
13. Do not use code fences.

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
Which road has the highest congestion?

Cypher:
MATCH (r:RoadSegment)-[:HAS_OBSERVATION]->(o:TrafficObservation)
RETURN r.segmentId, o.congestion_m, o.timestamp
ORDER BY o.congestion_m DESC
LIMIT 1

User question:
{question}
"""

        try:

            # -----------------------------
            # Generate Cypher using Ollama
            # -----------------------------

            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0
                    }
                },
                timeout=120
            )

            response.raise_for_status()

            cypher = response.json()["response"].strip()

            # Clean Qwen output

            cypher = cypher.replace("```cypher", "")
            cypher = cypher.replace("```", "")
            cypher = cypher.replace("\\:", ":")
            cypher = cypher.replace("\\_", "_")

            cypher = cypher.strip()

            # -----------------------------
            # Execute Cypher in Neo4j
            # -----------------------------

            with self.driver.session() as session:

                result = session.run(cypher)

                records = [
                    record.data()
                    for record in result
                ]

            # -----------------------------
            # Return result
            # -----------------------------

            return (
                f"Generated Cypher:\n"
                f"{cypher}\n\n"
                f"Neo4j Result:\n"
                f"{records}"
            )

        except Exception as e:

            return f"AP KG Error: {str(e)}"