# Neo4j implementation of GraphMemory
import logging

from dataclasses import asdict
from neo4j import GraphDatabase
import numpy as np
from .graph_result import GraphResult
from dma.utils import embed_text

from .graph_memory import GraphMemory
from dma.core import Memory, FeedbackType, Source, SourceType, TimeRelevance
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
            
        
        self._INDEX_NAME_VECTOR_EMBEDDINGS = "memory_embedding_index"
        

        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        
        if self.is_connected():
            self._create_db_if_not_exists()
        else:
            raise ConnectionError("Could not connect to Neo4j database.")
        
        self._init_db()
        
    def reset_database(self, CONFIRM_DELETE = False):
        """Reset the graph database by deleting all nodes and relationships.
        
        Parameters
        ----------
        CONFIRM_DELETE : bool
            Must be set to True to confirm deletion.
        
        Returns
        -------
        bool
            True if the database was reset successfully, False otherwise.
        """
        if not CONFIRM_DELETE:
            logging.warning("Database reset not confirmed. Set CONFIRM_DELETE=True to proceed.")
            return False
        
        try:
            with self.driver.session(database=self.database) as session:
                session.run("MATCH (n) DETACH DELETE n")
            logging.info("Database reset successfully.")
            self._init_db()
            return True
        except Exception as e:
            logging.error(f"Error resetting database: {e}")
            return False
        
    def _create_db_if_not_exists(self):
        # note: this requires the user to have admin privileges
        # and Neo4j enterprise edition
        # the community edition uses 'neo4j' as the default and only database
        pass
        #with self.driver.session() as session:
        #    session.run(f"CREATE DATABASE {self.database} IF NOT EXISTS")
            
    def _init_db(self):
        # create necessary indexes and constraints
        def create_constraints(tx):
            tx.run("""
            // Ensure uniqueness constraint on Memory id
            CREATE CONSTRAINT memory_id_unique IF NOT EXISTS
            FOR (m:Memory)
            REQUIRE m.id IS UNIQUE;
            """)
            
            tx.run("""
            // Ensure uniqueness constraint on Entity name
            CREATE CONSTRAINT entity_name_unique IF NOT EXISTS
            FOR (e:Entity)
            REQUIRE e.name IS UNIQUE;
            """)
            
            tx.run("""
            // Create vector index on Memory embedding
            CREATE VECTOR INDEX memory_embedding_index IF NOT EXISTS
            FOR (m:Memory)
            ON (m.embedding)
            OPTIONS { indexConfig: {
                `vector.dimensions`: 384,
                `vector.similarity_function`: 'cosine'
            }};
            """)
            
            tx.run("""
            // index last_access for faster sorting
            CREATE INDEX memory_last_access_index IF NOT EXISTS
            FOR (m:Memory)
            ON (m.last_access);
            """)
            
            tx.run("""
            // index memory time point for faster time-based queries
            CREATE INDEX memory_time_point_index IF NOT EXISTS
            FOR (m:Memory)
            ON (m.memory_time_point);
            """)
        
        def setup_storage_node(tx):
            tx.run("""
            // Setup general storage node
            MERGE (s:Storage {name: 'general_storage'})
            SET s.total_entity_connections = coalesce(s.total_entity_connections, 0)
            SET s.last_accessed = timestamp()
            SET s.first_created = coalesce(s.first_created, timestamp())
            SET s.purpose = coalesce(s.purpose, "General Knowledge")
            """)
            
        with self.driver.session(database=self.database) as session:
            session.execute_write(create_constraints)
            session.execute_write(setup_storage_node)

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
        
    def _record_to_memory(self, record) -> Memory:

        node = record['node']

        entities_dict = {}
        entities = record.get('entities', None)
        if entities is not None:
            for ent in entities:
                entities_dict[ent['name']] = ent['count']
                
        authors_list = record.get('authors', [])
        source = record.get('source', None)
            
        source_obj = None
        source_type = node.get('source_type', None)
        full_source = node.get('full_source', None)
        publisher = node.get('publisher', None)

        if source is not None:
            # print(f"Source type: {source_type}, full_source: {full_source}, source: {source}, authors: {authors_list}, publisher: {publisher}")
            source_obj = Source(
                source_type=SourceType(source_type) if source_type else SourceType.OTHER,
                full_source=full_source,
                source=source,
                authors=authors_list,
                publisher=publisher
            )
        elif full_source is not None and source_type is not None:
            source_obj = Source.from_source_type(
                source_type=SourceType(source_type),
                full_source=full_source,
                authors=authors_list,
                publisher=publisher
            )

        mem_dict = dict(node)
        # clear source fields that are now in source_obj
        if 'full_source' in mem_dict:
            del mem_dict['full_source']
        if 'source' in mem_dict:
            del mem_dict['source']
        if 'authors' in mem_dict:
            del mem_dict['authors']
        if 'publisher' in mem_dict:
            del mem_dict['publisher']
        if 'source_type' in mem_dict:
            del mem_dict['source_type']
        if source_obj is not None:
            mem_dict['source'] = source_obj
        mem_dict['embedding'] = np.array(mem_dict['embedding'])
        mem_dict['time_relevance'] = TimeRelevance(mem_dict['time_relevance'])
        memory = Memory(**mem_dict, entities=entities_dict)
        return memory
        
    def _add_memory(self, tx, memory: Memory) -> bool:
        mem_dict = asdict(memory)
        mem_dict['embedding'] = embed_text(memory.memory).tolist()  # convert np.ndarray to list for Neo4j storage
        mem_dict['time_relevance'] = memory.time_relevance.value  # store enum as its value
        mem_dict['full_source'] = memory.source.full_source if memory.source else None
        mem_dict['source'] = memory.source.source if memory.source else None
        mem_dict['authors'] = memory.source.authors if memory.source else []
        mem_dict['publisher'] = memory.source.publisher if memory.source else None
        mem_dict['source_type'] = memory.source.source_type.value if memory.source else None
        mem_dict['references'] = [source.source for source in memory.references] if memory.references else []
        
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
        
        result = tx.run(query, data=mem_dict, entities_list=entities_list)
        db_mem = result.single()
        
        return db_mem.get('mem_id', None) if db_mem else None
    
    def add_memory(self, memory: Memory) -> bool:
        try:
            with self.driver.session(database=self.database) as session:
                mem_id = session.execute_write(self._add_memory, memory)
                return mem_id == memory.id if mem_id is not None else mem_id is not None
        except Exception as e:
            logging.error(f"Error adding memory: {e}")
            return False
        
    def _add_memory_batch(self, tx, memories: list[Memory]) -> list[str]:
        # adds a batch of memories without connecting them
        mem_dicts = []
        for memory in memories:
            mem_dict = asdict(memory)
            mem_dict['embedding'] = embed_text(memory.memory).tolist()  # convert np.ndarray to list for Neo4j storage
            mem_dict['time_relevance'] = memory.time_relevance.value  # store enum as its value
            mem_dict["entities"] = [ {'name': name, 'count': count} for name, count in memory.entities.items()]
            mem_dict["full_source"] = memory.source.full_source if memory.source else None
            mem_dict["source"] = memory.source.source if memory.source else None
            mem_dict["authors"] = memory.source.authors if memory.source else []
            mem_dict["publisher"] = memory.source.publisher if memory.source else None
            mem_dict["source_type"] = memory.source.source_type.value if memory.source else None
            mem_dict["references"] = [source.source for source in memory.references] if memory.references else []
            
            mem_dicts.append(mem_dict)
            
        query = """
        UNWIND $mem_dicts AS data
        MERGE (m:Memory {id: data.id})
        SET m.memory = data.memory,
            m.topic = data.topic,
            m.truthfulness = data.truthfulness,
            m.embedding = data.embedding,
            m.memory_time_point = data.memory_time_point,
            m.full_source = data.full_source,
            m.publisher = data.publisher,
            m.source_type = data.source_type,
            m.creation_time = data.creation_time,
            m.last_access = data.last_access,
            m.total_access_count = data.total_access_count,
            m.positive_access_count = data.positive_access_count,
            m.negative_access_count = data.negative_access_count,
            m.time_relevance = data.time_relevance

        // Use CALL for optional author merging
        WITH m, data
        CALL (m, data) {
            WITH m, [author IN data.authors WHERE author IS NOT NULL] AS filtered_authors
            UNWIND filtered_authors AS author
            MERGE (a:Author {name: author})
            MERGE (m)-[:AUTHORED_BY]->(a)
        }
        
        // Use CALL for optional source merging
        WITH m, data
        CALL (m, data) {
            WITH m, data
            WHERE data.source IS NOT NULL 
            MERGE (s:Source {name: data.source})
            MERGE (m)-[:SOURCED_FROM]->(s)
        }
            
        // add entities and relationships
        // increase general storage total_entity_connections
        WITH m, data
        MATCH (s:Storage {name: 'general_storage'})
        SET s.total_entity_connections = s.total_entity_connections + size(data.entities)
        WITH m, data.entities as entities
        
        CALL(m, entities) {
            WITH m, entities
            UNWIND entities AS entity_data

            MERGE (e:Entity {name: entity_data.name})
            MERGE (m)-[men:MENTIONS]->(e)
                ON CREATE SET men.isNew = true
                ON CREATE SET e.mentionsCount = COALESCE(e.mentionsCount, 0) + 1
            SET men.count = entity_data.count
            
            // Collect all entities for this memory
            WITH m, collect(e) AS entity_nodes 

            // 1. Run co-mention logic in an ISOLATED subquery.
            //    This subquery can produce 0 rows (for 1-entity memories)
            //    without stopping the main flow.
            CALL(m, entity_nodes) {
                WITH m, entity_nodes // Import the full list
                UNWIND entity_nodes AS e1
                UNWIND entity_nodes AS e2
                WITH m, e1, e2
                WHERE e1.name < e2.name
                
                MATCH (m)-[men1:MENTIONS]->(e1)
                MATCH (m)-[men2:MENTIONS]->(e2)
                WHERE men1.isNew = true OR men2.isNew = true
                
                MERGE (e1)-[r:MENTIONED_WITH]->(e2)
                    ON CREATE SET r.coMentionCount = 1
                    ON MATCH SET r.coMentionCount = r.coMentionCount + 1
            }
            
            // 2. Cleanup logic.
            //    This code runs *after* the subquery is complete.
            //    'm' and 'entity_nodes' are still in scope from the 'WITH'
            //    *before* the subquery.
            //    This part is no longer affected by the 0-row result
            //    of the co-mention logic.
            
            UNWIND entity_nodes AS e_node
            MATCH (m)-[men:MENTIONS]->(e_node)
            WHERE men.isNew = true
            REMOVE men.isNew
        }
        
        WITH m
        
        RETURN m.id AS mem_id   
        """
        result = tx.run(query, mem_dicts=mem_dicts)

        ids = [record.get('mem_id', None) for record in result]
        ids = [id for id in ids if id is not None]
        if len(ids) != len(memories):
            logging.warning(f"Warning: only {len(ids)} out of {len(memories)} memories were added successfully.")
        return ids
    
    def add_memory_batch(self, memories: list[Memory]) -> list[str]:
        try:
            with self.driver.session(database=self.database) as session:
                mem_ids = session.execute_write(self._add_memory_batch, memories)
                return mem_ids
        except Exception as e:
            logging.error(f"Error adding memory batch: {e}")
            return []
        
    def _add_memory_series(self, tx, memories: list[Memory]) -> bool:
        # adds a series of memories and connects them in sequence
        # for example, memories from a single text
        # connects each memory to the next one in the series
        mem_dicts = []
        for memory in memories:
            mem_dict = asdict(memory)
            mem_dict['embedding'] = embed_text(memory.memory).tolist()  # convert np.ndarray to list for Neo4j storage
            mem_dict['time_relevance'] = memory.time_relevance.value  # store enum as its value
            mem_dict["entities"] = [ {'name': name, 'count': count} for name, count in memory.entities.items()]
            mem_dict["full_source"] = memory.source.full_source if memory.source else None
            mem_dict["source"] = memory.source.source if memory.source else None
            mem_dict["authors"] = memory.source.authors if memory.source else []
            mem_dict["publisher"] = memory.source.publisher if memory.source else None
            mem_dict["source_type"] = memory.source.source_type.value if memory.source else None
            # TODO: implement references in batch add
            mem_dict["references"] = [source.source for source in memory.references] if memory.references else []
            
            mem_dicts.append(mem_dict)
            
        query = """
        UNWIND $mem_dicts AS data
        MERGE (m:Memory {id: data.id})
        SET m.memory = data.memory,
            m.topic = data.topic,
            m.truthfulness = data.truthfulness,
            m.embedding = data.embedding,
            m.memory_time_point = data.memory_time_point,
            m.full_source = data.full_source,
            m.publisher = data.publisher,
            m.source_type = data.source_type,
            m.creation_time = data.creation_time,
            m.last_access = data.last_access,
            m.total_access_count = data.total_access_count,
            m.positive_access_count = data.positive_access_count,
            m.negative_access_count = data.negative_access_count,
            m.time_relevance = data.time_relevance

        // Use CALL for optional author merging
        WITH m, data
        CALL (m, data) {
            WITH m, [author IN data.authors WHERE author IS NOT NULL] AS filtered_authors
            UNWIND filtered_authors AS author
            MERGE (a:Author {name: author})
            MERGE (m)-[:AUTHORED_BY]->(a)
        }
        
        // Use CALL for optional source merging
        WITH m, data
        CALL (m, data) {
            WITH m, data
            WHERE data.source IS NOT NULL 
            MERGE (s:Source {name: data.source})
            MERGE (m)-[:SOURCED_FROM]->(s)
        }
            
        // add entities and relationships
        // increase general storage total_entity_connections
        WITH m, data
        MATCH (s:Storage {name: 'general_storage'})
        SET s.total_entity_connections = s.total_entity_connections + size(data.entities)
        
        WITH m, data.entities as entities
        
        CALL(m, entities) {
            WITH m, entities
            UNWIND entities AS entity_data

            MERGE (e:Entity {name: entity_data.name})
            MERGE (m)-[men:MENTIONS]->(e)
                ON CREATE SET men.isNew = true
                ON CREATE SET e.mentionsCount = COALESCE(e.mentionsCount, 0) + 1
            SET men.count = entity_data.count
            
            // Collect all entities for this memory
            WITH m, collect(e) AS entity_nodes 

            // 1. Run co-mention logic in an ISOLATED subquery.
            //    This subquery can produce 0 rows (for 1-entity memories)
            //    without stopping the main flow.
            CALL(m, entity_nodes) {
                WITH m, entity_nodes // Import the full list
                UNWIND entity_nodes AS e1
                UNWIND entity_nodes AS e2
                WITH m, e1, e2
                WHERE e1.name < e2.name
                
                MATCH (m)-[men1:MENTIONS]->(e1)
                MATCH (m)-[men2:MENTIONS]->(e2)
                WHERE men1.isNew = true OR men2.isNew = true
                
                MERGE (e1)-[r:MENTIONED_WITH]->(e2)
                    ON CREATE SET r.coMentionCount = 1
                    ON MATCH SET r.coMentionCount = r.coMentionCount + 1
            }
            
            // 2. Cleanup logic.
            //    This code runs *after* the subquery is complete.
            //    'm' and 'entity_nodes' are still in scope from the 'WITH'
            //    *before* the subquery.
            //    This part is no longer affected by the 0-row result
            //    of the co-mention logic.
            
            UNWIND entity_nodes AS e_node
            MATCH (m)-[men:MENTIONS]->(e_node)
            WHERE men.isNew = true
            REMOVE men.isNew
        }
        
        WITH collect(DISTINCT m) AS mems
        CALL(mems) {
            WITH mems
            UNWIND range(0, size(mems) - 2) AS idx
            WITH mems[idx] AS m1, mems[idx + 1] AS m2
            MERGE (m1)-[r:NEXT_IN_SERIES]->(m2)
        }
        RETURN [m IN mems | m.id] AS connected_mem_ids
        """
        result = tx.run(query, mem_dicts=mem_dicts)
        
        ids = result.single().get('connected_mem_ids', [])
        ids = [id for id in ids if id is not None]
        if len(ids) != len(memories):
            print(f"Warning: only {len(ids)} out of {len(memories)} memories were added successfully.")
        return ids
    
    def add_memory_series(self, memories: list[Memory]) -> bool:

        try:
            with self.driver.session(database=self.database) as session:
                added_ids = session.execute_write(self._add_memory_series, memories)
            return len(added_ids) == len(memories)
        except Exception as e:
            logging.error(f"Error adding memory series: {e}")
            return False
        
    def _query_memories_by_id(self, tx, memory_ids: list[str]) -> list[Memory]:
        query = """
        UNWIND $memory_ids AS mem_id
        MATCH (m:Memory {id: mem_id})

        OPTIONAL MATCH (m)-[:SOURCED_FROM]->(s:Source) 

        RETURN m AS node, 
            // Collect all MENTIONS relationships as a list (Prevents duplication)
            [(m)-[men:MENTIONS]->(e:Entity) | {name: e.name, count: men.count}] AS entities, 
            // Collect all AUTHORED_BY relationships as a list (Prevents duplication)
            [(m)-[:AUTHORED_BY]->(a:Author) | a.name] AS authors, 
            // Source is a single value, pulled from the safe OPTIONAL MATCH
            s.name AS source
        """
        result = tx.run(query, memory_ids=memory_ids)
        if result is None:
            return []
        return [self._record_to_memory(record) for record in result]
    
    def query_memories_by_id(self, memory_ids: list[str]) -> list[Memory]:
        try:
            with self.driver.session(database=self.database) as session:
                memories = session.execute_read(self._query_memories_by_id, memory_ids)
                return memories
        except Exception as e:
            logging.error(f"Error querying memories by id: {e}")
            return []
        
    def _query_memories_by_entities(self, tx, entities: list[str], limit: int = 10) -> list[GraphResult]:
        # for each entity in the list, find memories that mention it
        # and then rank by number of other entities from the list mentioned in the memory
        query = """
        // 1. Unwind your input list of primary entities
        UNWIND $entity_names AS primary_name

        // 2. Find the primary entity and all memories mentioning it
        MATCH (primary_e:Entity {name: primary_name})<-[:MENTIONS]-(m:Memory)

        // 3. For each (primary_name, m) pair (100,000 rows),
        //    calculate the diversity score *without* adding rows.
        WITH primary_name, m,
            // This sub-query in brackets runs for each 'm'
            // It counts how many *other* entities from the list 'm' mentions
            COUNT {
                MATCH (m)-[:MENTIONS]->(other_e:Entity)
                WHERE other_e.name IN $entity_names AND other_e.name <> primary_name
            } AS diversity_score

        // 4. Now sort the 100,000 rows. This is still the main cost,
        //    but it's far better than sorting 900,000.
        ORDER BY primary_name, diversity_score DESC, m.last_access DESC

        // 5. Collect into 10 groups (one per primary_name)
        WITH primary_name, COLLECT({memory: m, score: diversity_score}) AS ranked_memories

        // 6. Slice the top 'n' from each group
        UNWIND ranked_memories[0..$top_n] AS result_data

        // 7. Efficiently fetch the *full* entity list for the final,
        //    filtered memories (e.g., 10 * n rows)
        WITH primary_name,
            result_data.memory AS m,
            result_data.score AS diversity_score,
            [(m)-[men:MENTIONS]->(e_all:Entity) | {name: e_all.name, count: men.count}] AS entities,
            [(m)-[:AUTHORED_BY]->(a:Author) | a.name] AS authors,
            head([(m)-[:SOURCED_FROM]->(s:Source) | s.name]) AS source

        RETURN primary_name, m AS node, diversity_score, entities, authors, source
        """
        result = tx.run(query, entity_names=entities, top_n=limit)
        memories = {}
        for record in result:
            primary_name = record['primary_name']
            memory = self._record_to_memory(record)
            score = record['diversity_score']
            if primary_name not in memories:
                memories[primary_name] = []
            memories[primary_name].append((memory, score))
        return memories
    
    def query_memories_by_entities(self, entities: list[str], limit: int = 10) -> dict[list[GraphResult]]:
        try:
            with self.driver.session(database=self.database) as session:
                mem_dict = session.execute_read(self._query_memories_by_entities, entities, limit)
                
                result_dict = {}
                for entity, mem_list in mem_dict.items():
                    result_dict[entity] = [GraphResult(memory=mem, score=score) for mem, score in mem_list]
                
                return result_dict
        except Exception as e:
            logging.error(f"Error querying memories by entities: {e}")
            return {}
        
    def _query_memories_by_vector(self, tx, vector: list[float], top_k: int = 10) -> list[GraphResult]:
        index_name = self._INDEX_NAME_VECTOR_EMBEDDINGS
        query = """
        CALL db.index.vector.queryNodes($index_name, $top_k, $embedding)
        YIELD node, score

        // --- FIX IS HERE ---
        OPTIONAL MATCH (node)-[:SOURCED_FROM]->(s:Source)

        WITH node, score, 
            [(node)-[men:MENTIONS]->(e:Entity) | {name: e.name, count: men.count}] AS entities, 
            [(node)-[:AUTHORED_BY]->(a:Author) | a.name] AS authors, 
            s.name AS source // This will be null if s is null
        RETURN node, score, entities, authors, source
        ORDER BY score DESC
        // LIMIT $top_k // This is probably not needed, see note below
        """
        result = tx.run(query, embedding=vector, top_k=top_k, index_name=index_name)
        return [(self._record_to_memory(record), record['score']) for record in result]
    
    def query_memories_by_vector(self, vector: list[float], top_k: int = 10) -> list[GraphResult]:
        try:
            with self.driver.session(database=self.database) as session:
                mem_list = session.execute_read(self._query_memories_by_vector, vector, top_k)
                return [GraphResult(memory=mem, score=score) for mem, score in mem_list]
        except Exception as e:
            logging.error(f"Error querying memories by vector: {e}")
            return []
        
    def _connect_memories(self, tx, memory_ids: list[str]) -> bool:
        # connects or strengthens relationships between memories
        # basically, memories that are often accessed together are linked more strongly
        query = """
        UNWIND $mem_ids AS mem_id1
        UNWIND $mem_ids AS mem_id2
        WITH mem_id1, mem_id2
        WHERE mem_id1 < mem_id2  // avoid self-relationships and duplicate pairs
        MATCH (m1:Memory {id: mem_id1})
        MATCH (m2:Memory {id: mem_id2})
        MERGE (m1)-[r:RELATED_TO]->(m2)
            ON CREATE SET r.connection_strength = 1
            ON MATCH SET r.connection_strength = r.connection_strength + 1
        """
        tx.run(query, mem_ids=memory_ids)

        return True

    def connect_memories(self, memory_ids: list[str]) -> bool:
        try:
            with self.driver.session(database=self.database) as session:
                result = session.execute_write(self._connect_memories, memory_ids)
                return result
        except Exception as e:
            logging.error(f"Error connecting memories: {e}")
            return False
        
    def _query_related_memories(self, tx, memory_id: str, top_k: int = 10) -> list[GraphResult]:
        query = """
        MATCH (m:Memory {id: $mem_id})-[r:RELATED_TO]-(related:Memory)
        OPTIONAL MATCH (related)-[:SOURCED_FROM]->(s:Source)
        
        // sort by connection strength and return top k
        RETURN related AS node, r.connection_strength AS strength,
            [(related)-[men:MENTIONS]->(e:Entity) | {name: e.name, count: men.count}] AS entities,
            [(related)-[:AUTHORED_BY]->(a:Author) | a.name] AS authors,
            s.name AS source
        ORDER BY r.connection_strength DESC
        LIMIT $top_k
        """
        result = tx.run(query, mem_id=memory_id, top_k=top_k)

        return [(self._record_to_memory(record), record['strength']) for record in result]
    
    def query_related_memories(self, memory_id: str, top_k: int = 10) -> list[GraphResult]:
        try:
            with self.driver.session(database=self.database) as session:
                mem_list = session.execute_read(self._query_related_memories, memory_id, top_k)
                return [GraphResult(memory=mem, score=strength) for mem, strength in mem_list]
        except Exception as e:
            logging.error(f"Error querying related memories: {e}")
            return []
        
    def _update_memory_access(self, tx, memories: list[str], feedback: FeedbackType=FeedbackType.NEUTRAL) -> list[str]:
        query = """
        UNWIND $mem_ids AS mem_id
        MATCH (m:Memory {id: mem_id})
        SET m.last_access = timestamp(),
            m.total_access_count = coalesce(m.total_access_count, 0) + 1
        
        RETURN m.id AS mem_id
        """
        
        if feedback == FeedbackType.POSITIVE:
            query += ", m.positive_access_count = coalesce(m.positive_access_count, 0) + 1"
        elif feedback == FeedbackType.NEGATIVE:
            query += ", m.negative_access_count = coalesce(m.negative_access_count, 0) + 1"

        result = tx.run(query, mem_ids=memories)
        ids = [record.get('mem_id', None) for record in result]
        ids = [id for id in ids if id is not None]
        return ids
        
    def update_memory_access(self, memories: list[str], feedback: FeedbackType=FeedbackType.NEUTRAL) -> list[str]:
        try:
            with self.driver.session(database=self.database) as session:
                return session.execute_write(self._update_memory_access, memories, feedback)
        except Exception as e:
            logging.error(f"Error updating memory access: {e}")
            return []
        
    def _query_memory_series(self, tx, origin_memory_id: str, previous_n: int = 2, next_n: int = 2) -> list[Memory]:
        """
        Fetches a single series of Memory nodes centered around an origin,
        going back 'previous' steps and forward 'next' steps.
        
        
        """

        if not isinstance(previous_n, int) or previous_n < 0:
            previous_n = 2
        if not isinstance(next_n, int) or next_n < 0:
            next_n = 2

        query = """
        // 1. Find the origin node
        MATCH (origin:Memory {id: $origin_id})"""+f"""

        // 2. Find all paths ending at origin, pick the longest one within limit
        OPTIONAL MATCH path_prev = (prev_mem:Memory)-[:NEXT_IN_SERIES*0..{previous_n}]->(origin)
        WITH origin, path_prev
        ORDER BY length(path_prev) DESC
        LIMIT 1

        // 3. Get nodes from that path. Default to [origin] if no path found.
        //    The path list is ordered: [earliest_node, ..., origin]
        WITH origin, coalesce(nodes(path_prev), [origin]) AS prev_path_nodes

        // 4. Find all paths starting at origin, pick the longest one within limit
        OPTIONAL MATCH path_next = (origin)-[:NEXT_IN_SERIES*0..{next_n}]->(next_mem:Memory)
        WITH prev_path_nodes, path_next, origin
        ORDER BY length(path_next) DESC
        LIMIT 1

        // 5. Get nodes from that path. Default to [origin] if no path found.
        //    The path list is ordered: [origin, ..., latest_node]
        WITH prev_path_nodes, coalesce(nodes(path_next), [origin]) AS next_path_nodes

        // 6. Combine the lists.
        //    prev_path_nodes[0..-1] takes all nodes *except* the last one (the origin)
        //    + next_path_nodes appends the list that *starts* with the origin
        //    This creates the final de-duplicated, ordered list.
        WITH prev_path_nodes[0..-1] + next_path_nodes AS memory_series
        UNWIND memory_series AS m
        OPTIONAL MATCH (m)-[:SOURCED_FROM]->(s:Source)""" +"""
        RETURN m AS node,
            s.name AS source,
            [(m)-[men:MENTIONS]->(e:Entity) | {name: e.name, count: men.count}] AS entities,
            [(m)-[:AUTHORED_BY]->(a:Author) | a.name] AS authors
        
        """
        result = tx.run(query, origin_id=origin_memory_id)
        return [self._record_to_memory(record) for record in result]
    
    def query_memory_series(self, origin_memory_id: str, previous: int = 2, next: int = 2) -> list[Memory]:
        try:
            with self.driver.session(database=self.database) as session:
                memories = session.execute_read(self._query_memory_series, origin_memory_id, previous, next)
                return memories
        except Exception as e:
            logging.error(f"Error querying memory series: {e}")
            return []
        
    def _deep_relationship_traversal(self, tx, memory_id: str, max_depth: int = 3, stop_k: int = 50, blacklist_ids: list[str] = []) -> list[GraphResult]:
        query = """
        // Start from your origin node
        MATCH (start:Memory {id: $originId})

        // Call the APOC path expander
        CALL apoc.path.expandConfig(start, {
            maxLevel: $maxDepth,
            bfs: true,                  // Use Breadth-First Search
            uniqueness: 'NODE_GLOBAL'   // Visit each node only once
            // use blacklistNodes to stop traversal at blacklisted nodes
        }) YIELD path

        // Get the end node of each path
        WITH last(nodes(path)) AS end, length(path) AS depth

        // Filter for :Memory nodes, exclude the start node,
        // AND apply the blacklist
        WHERE end:Memory
        AND end.id <> $originId
        AND NOT end.id IN $blacklist  // ◀ NEW: Exclude blacklisted IDs

        // Order by depth and apply your limit
        ORDER BY depth
        LIMIT $maxResults
        OPTIONAL MATCH (end)-[:SOURCED_FROM]->(s:Source)

        RETURN end as node, depth, s.name AS source,
            [(end)-[men:MENTIONS]->(e:Entity) | {name: e.name, count: men.count}] AS entities,
            [(end)-[:AUTHORED_BY]->(a:Author) | a.name] AS authors
        """
        
        result = tx.run(query, originId=memory_id, maxDepth=max_depth, maxResults=stop_k, blacklist=blacklist_ids)
        return [(self._record_to_memory(record), 1 / max(record['depth'], 0.5)) for record in result]
    
    def deep_relationship_traversal(self, memory_id: str, max_depth: int = 3, stop_k: int = 50, blacklist_ids: list[str] = []) -> list[GraphResult]:
        try:
            with self.driver.session(database=self.database) as session:
                mem_list = session.execute_read(self._deep_relationship_traversal, memory_id, max_depth, stop_k, blacklist_ids)
                return [GraphResult(memory=mem, score=score) for mem, score in mem_list]
        except Exception as e:
            logging.error(f"Error in deep relationship traversal: {e}")
            return []