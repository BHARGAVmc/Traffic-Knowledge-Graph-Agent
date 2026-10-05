import pandas as pd
from neo4j import GraphDatabase

# =========================
# Neo4j Configuration
# =========================

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password123"

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD)
)

# =========================
# Files
# =========================

DATA_FILE = "synthetic_data/AP_TrafficData.csv"
METADATA_FILE = "synthetic_data/road_segments.csv"


# =========================
# Create Graph
# =========================

def create_graph():

    traffic_df = pd.read_csv(DATA_FILE)
    metadata_df = pd.read_csv(METADATA_FILE)

    print("Traffic data:", traffic_df.shape)
    print("Road metadata:", metadata_df.shape)

    with driver.session() as session:

        # ---------------------------------
        # Clear previous AP test graph
        # ---------------------------------

        print("\nClearing previous AP graph...")

        session.run("""
        MATCH (n)
        WHERE n:APDistrict
           OR n:RoadSegment
           OR n:TrafficObservation
           OR n:TrafficTime
        DETACH DELETE n
        """)

        # ---------------------------------
        # Create Districts and Road Segments
        # ---------------------------------

        print("Creating districts and road segments...")

        for _, row in metadata_df.iterrows():

            district = row["district"]
            segment_id = row["segment_id"]
            linestring = row["linestring"]
            length_m = float(row["length_m"])

            session.run("""
            MERGE (d:APDistrict {name: $district})

            MERGE (r:RoadSegment {segmentId: $segment_id})

            SET r.linestring = $linestring,
                r.length_m = $length_m

            MERGE (d)-[:CONTAINS]->(r)
            """,
            district=district,
            segment_id=segment_id,
            linestring=linestring,
            length_m=length_m)

        # ---------------------------------
        # Create Traffic Observations
        # ---------------------------------

        print("Creating traffic observations...")

        segment_columns = [
            column
            for column in traffic_df.columns
            if column != "Timestamp"
        ]

        # Map LINESTRING -> segment ID
        segment_map = dict(
            zip(
                metadata_df["linestring"],
                metadata_df["segment_id"]
            )
        )

        for _, row in traffic_df.iterrows():

            timestamp = row["Timestamp"]

            for column in segment_columns:

                segment_id = segment_map.get(column)

                if segment_id is None:
                    continue

                congestion = float(row[column])

                # Create time node
                session.run("""
                MERGE (time:TrafficTime {
                    timestamp: $timestamp
                })
                """,
                timestamp=timestamp)

                # Create observation
                session.run("""
                MATCH (r:RoadSegment {
                    segmentId: $segment_id
                })

                MATCH (time:TrafficTime {
                    timestamp: $timestamp
                })

                CREATE (o:TrafficObservation {
                    congestion_m: $congestion,
                    timestamp: $timestamp
                })

                CREATE (r)-[:HAS_OBSERVATION]->(o)

                CREATE (o)-[:AT_TIME]->(time)
                """,
                segment_id=segment_id,
                timestamp=timestamp,
                congestion=congestion)

    print("\n===================================")
    print("AP KNOWLEDGE GRAPH CREATED")
    print("===================================")


# =========================
# Main
# =========================

if __name__ == "__main__":

    try:
        create_graph()

    except Exception as e:
        print("\nNeo4j Error:")
        print(e)

    finally:
        driver.close()