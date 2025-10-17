# Neo4j implementation of GraphMemory

from neo4j import GraphDatabase

from .graph_memory import GraphMemory
from dma.core import Memory


class Neo4jMemory(GraphMemory):
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        self._create_database_if_not_exists()
        
    def _create_database_if_not_exists(self):
        with self.driver.session() as session:
            session.run(f"CREATE DATABASE {self.database} IF NOT EXISTS")
        
    def close(self):
        self.driver.close()

    def add_memory(self, memory: Memory):
        
        # example, not actually implemented
        result = self.driver.execute_query(
            """
            CREATE (m:Memory {
                id: randomUUID(),
                memory: $memory,
                memory_time_point: datetime($memory_time_point),
                time_relevance: $time_relevance,
                truthfulness: $truthfulness
            })
            RETURN m.id AS memory_id
            """,
            memory=memory.memory,
            memory_time_point=memory.memory_time_point.isoformat(),
            time_relevance=memory.time_relevance,
            truthfulness=memory.truthfulness
        )
        memory_id = result.single()["memory_id"]
        
        # id as indexed property
        # (so we can access memories we get from vector db)
        
        # add entities and relationships
        # entities as nodes
        
        # sources as nodes
        
        # timestamp as indexed property
        # (each of creation, last accessed, memory time point)
    
    
        
        
        
        
        