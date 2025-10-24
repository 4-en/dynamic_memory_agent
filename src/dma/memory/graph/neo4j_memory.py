# Neo4j implementation of GraphMemory
import logging

from dataclasses import asdict
from neo4j import GraphDatabase
from .graph_result import GraphResult
from dma.utils import embed_text

from .graph_memory import GraphMemory
from dma.core import Memory, FeedbackType
import os


class Neo4jMemory(GraphMemory):
    def __init__(
        self,
        uri: str = "neo4j://localhost:7687",
        user: str = "neo4j",
        password: str = "testtest",
        database: str = "neo4j"
    ):
        
        # use following priority to get connection info:
        # 1. parameters if non default
        # 2. environment variables
        # 3. default values

        if uri == "neo4j://localhost:7687":
            uri = os.getenv("NEO4J_URI", uri)
        if user == "neo4j":
            user = os.getenv("NEO4J_USER", user)
        if password == "testtest":
            password = os.getenv("NEO4J_PASSWORD", password)
        if database == "neo4j":
            database = os.getenv("NEO4J_DATABASE", database)
        

        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        
        if self.is_connected():
            self._create_db_if_not_exists()
        else:
            raise ConnectionError("Could not connect to Neo4j database.")
        
    def _create_db_if_not_exists(self):
        # note: this requires the user to have admin privileges
        # and Neo4j enterprise edition
        # the community edition uses 'neo4j' as the default and only database
        with self.driver.session() as session:
            session.run(f"CREATE DATABASE {self.database} IF NOT EXISTS")

    def is_connected(self) -> bool:
        """Check if the graph database is connected.
        
        Returns
        -------
        bool
            True if connected, False otherwise.
        """
        try:
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1")
            return True
        except Exception:
            return False
        
    def _add_memory(self, tx, memory: Memory) -> bool:
        mem_dict = asdict(memory)
        mem_dict['embedding'] = embed_text(memory.memory).tolist()  # convert np.ndarray to list for Neo4j storage
        mem_dict['time_relevance'] = memory.time_relevance.value  # store enum as its value
        mem_dict['full_source'] = memory.source.full_source if memory.source else None
        mem_dict['source'] = memory.source.source if memory.source else None
        mem_dict['authors'] = memory.source.authors if memory.source else []
        mem_dict['publisher'] = memory.source.publisher if memory.source else None
        mem_dict['source_type'] = memory.source.source_type.value if memory.source else None
        
        entities_list = [ {'name': name, 'count': count} for name, count in memory.entities.items()]
        
        query = """
        // Create or find the main node
        MERGE (m:Memory {id: $data.id})
        SET m.memory = $data.memory,
            m.topic = $data.topic,
            m.truthfulness = $data.truthfulness,
            m.embedding = $data.embedding,
            m.memory_time_point = $data.memory_time_point,
            m.full_source = $data.full_source,
            m.publisher = $data.publisher,
            m.source_type = $data.source_type,
            m.creation_time = $data.creation_time,
            m.last_access = $data.last_access,
            m.total_access_count = $data.total_access_count,
            m.positive_access_count = $data.positive_access_count,
            m.negative_access_count = $data.negative_access_count,
            m.time_relevance = $data.time_relevance
            
        // Use CALL for optional author merging
        // This pattern is correct for a LIST
        WITH m
        CALL (m) {
            // Filter the list *before* unwinding
            WITH m, [author IN $data.authors WHERE author IS NOT NULL] AS filtered_authors
            UNWIND filtered_authors AS author
            MERGE (a:Author {name: author})
            MERGE (m)-[:AUTHORED_BY]->(a)
        }
        
        // Use CALL for optional source merging
        // This pattern is correct for a SINGLE VALUE
        WITH m
        CALL (m) {
            // 2. Add a 'normal' WITH statement *after* the import.
            // This satisfies the syntax requirement.
            WITH m
            // 2. Now, do your logic using the '$data' parameter
            WHERE $data.source IS NOT NULL 
            MERGE (s:Source {name: $data.source})
            MERGE (m)-[:SOURCED_FROM]->(s)
        }
        
        // increase general storage total_entity_connections
        WITH m
        MATCH (s:Storage {name: 'general_storage'})
        SET s.total_entity_connections = s.total_entity_connections + size($entities_list)
        
        // create entities and relationships
        WITH m
        CALL (m) {
            WITH m
            UNWIND $entities_list AS entity_data
            MERGE (e:Entity {name: entity_data.name})
            MERGE (m)-[men:MENTIONS]->(e)
                ON CREATE SET e.mentionsCount = COALESCE(e.mentionsCount, 0) + 1
            SET men.count = entity_data.count

        
            // add relationships between entities mentioned in this memory
            WITH m, collect(e) AS entities
            UNWIND entities AS e1
            UNWIND entities AS e2
            WITH e1, e2, m
            WHERE e1.name < e2.name
            // if this query is used as an update, this will incorrectly double count co-mentions
            // therefore, use different method for updates or recalculate after batch updates
            MERGE (e1)-[r:MENTIONED_WITH]->(e2)
                ON CREATE SET r.coMentionCount = 1
                ON MATCH SET r.coMentionCount = r.coMentionCount + 1
        }
            
        RETURN m.id AS mem_id
        """
        
        # TODO: also create Entity nodes and relationships
        # also nodes and relationships for source if applicable
        
        result = tx.run(query, data=mem_dict, entities_list=entities_list)
        db_mem = result.single()
        
        return db_mem.get('mem_id', None) if db_mem else None
    
    def add_memory(self, memory: Memory) -> bool:
        try:
            with self.driver.session(database=self.database) as session:
                mem_id = session.write_transaction(self._add_memory, memory)
                return mem_id is not None
        except Exception as e:
            logging.error(f"Error adding memory: {e}")
            return False

        
        