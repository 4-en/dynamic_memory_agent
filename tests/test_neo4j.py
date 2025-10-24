# neo4j test
# tests adding Memories to Neo4j and retrieving them

from dma.core import Memory, TimeRelevance, FeedbackType
from dma.core.sources import Source, SourceType
from dma.utils import embed_text, cosine_similarity
from dataclasses import asdict
import time
from neo4j import GraphDatabase
import json
import numpy as np

def initialize_db(session):
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
        
    session.execute_write(create_constraints)
    session.execute_write(setup_storage_node)
    
def recalculate_entity_mentions(tx):
    # Recalculate mentionsCount for all entities
    query = """
    MATCH (e:Entity)
    OPTIONAL MATCH (m:Memory)-[men:MENTIONS]->(e)
    WITH e, COUNT(m) AS mention_count
    SET e.mentionsCount = mention_count
    """
    tx.run(query)
    
    # update total_entity_connections in storage
    query = """
    MATCH (s:Storage {name: 'general_storage'})
    MATCH (e:Entity)
    WITH s, COUNT(e.mentionsCount) AS total_connections
    SET s.total_entity_connections = total_connections
    """
    tx.run(query)
    
    

memories = []
sample_texts = [
    "The James Webb Space Telescope (JWST) has a primary mirror with a diameter of 6.5 meters (21.3 feet), which gives it a collecting area of approximately 25.4 square meters. This significantly larger size compared to previous telescopes allows it to gather more light, enabling it to see objects that are older, more distant, or fainter.",
    "Unlike Hubble's single, monolithic mirror, the JWST's primary mirror is composed of 18 individual hexagonal segments. Each segment is made of beryllium, which is both strong and lightweight, and is coated with a microscopically thin layer of gold to optimize its reflectivity for infrared light. These segments had to be folded to fit inside the rocket fairing for launch and were later unfolded in space.",
    "The Hubble Space Telescope (HST) utilizes a primary mirror that is 2.4 meters (7.9 feet) in diameter, with a collecting area of about 4.5 square meters. It is a single-piece, polished glass mirror coated with layers of aluminum and magnesium fluoride. This design is optimized for observing in the near-ultraviolet, visible, and near-infrared spectra.",
    "Hubble's mirror is a monolithic structure, meaning it is made from a single piece of glass. This design choice provides high optical quality and stability, which is essential for the precise observations Hubble conducts. The mirror's surface was polished to an accuracy of about 10 nanometers, allowing it to capture sharp images of distant celestial objects."
]

for i, text in enumerate(sample_texts):
    memory = Memory(
        memory=text,
        id=f"test_memory_{i}",
        time_relevance=TimeRelevance.MONTH,
        memory_time_point=time.time() - i * 86400 * 7,  # spaced a week apart
        
    )
    
    if i == 0:
        # add a source for first memory
        memory.source = Source.from_web("https://example.com/jwst", authors=["Jane Doe", "John Smith"], publisher="Example Publisher")
    
    elif i == 2:
        memory.entities = {}
    
    print(f"Created memory with id: {memory.id} and embedding shape: {memory.embedding.shape}")
    memories.append(memory)
    
driver = GraphDatabase.driver("neo4j://localhost:7687", auth=("neo4j", "testtest"))

# check if we are connected
with driver.session() as session:
    result = session.run("RETURN 1")
    print("Connected to Neo4j:", result.single()[0] == 1)
    
def clear_db(tx):
    tx.run("MATCH (n) DETACH DELETE n")
    

def merge_dict_query(node_label: str, data: dict, key_field: str) -> str:
    set_statements = ",\n".join([f"    n.{k} = $data.{k}" for k in data.keys() if k != key_field])
    query = f"""
    MERGE (n:{node_label} {{{key_field}: $data.{key_field}}})
    SET {set_statements}
    """

    return query

def record_to_memory(record) -> Memory:

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

def add_memory(tx, memory: Memory) -> str:
    """Add a memory to the database.
    
    Parameters
    ----------
    tx : neo4j.Transaction
        The Neo4j transaction object.
    memory : Memory
        The memory object to add to the database.

    Returns
    -------
    str
        The ID of the added/updated memory, or None if failed.
    """
    mem_id = memory.id
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

    
    result = tx.run(query, data=mem_dict, entities_list=entities_list)
    db_mem = result.single()
    
    return db_mem.get('mem_id', None) if db_mem else None

def find_similar_memories(tx, embedding: list, top_k: int = 5):
    index_name = "memory_embedding_index"
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
    result = tx.run(query, embedding=embedding, top_k=top_k, index_name=index_name)
    return [(record_to_memory(record), record['score']) for record in result]

def find_memory_by_id(tx, mem_id: str) -> Memory | None:
    query = """
    MATCH (m:Memory {id: $mem_id})
    OPTIONAL MATCH (m)-[men:MENTIONS]->(e:Entity)
    OPTIONAL MATCH (m)-[:AUTHORED_BY]->(a:Author)
    OPTIONAL MATCH (m)-[:SOURCED_FROM]->(s:Source)

    RETURN m AS node, [(m)-[men:MENTIONS]->(e:Entity) | {name: e.name, count: men.count}] AS entities, 
           [(m)-[:AUTHORED_BY]->(a:Author) | a.name] AS authors, 
           s.name AS source
    """
    result = tx.run(query, mem_id=mem_id)
    record = result.single()
    if record is None:
        return None
    return record_to_memory(record)

def update_memory_access(tx, memories: list[str], feedback: FeedbackType=FeedbackType.NEUTRAL):
    query = """
    UNWIND $mem_ids AS mem_id
    MATCH (m:Memory {id: mem_id})
    SET m.last_access = timestamp(),
        m.total_access_count = coalesce(m.total_access_count, 0) + 1
    """
    
    if feedback == FeedbackType.POSITIVE:
        query += ", m.positive_access_count = coalesce(m.positive_access_count, 0) + 1"
    elif feedback == FeedbackType.NEGATIVE:
        query += ", m.negative_access_count = coalesce(m.negative_access_count, 0) + 1"

    tx.run(query, mem_ids=memories)
    
def connect_memories(tx, memory_ids: list[str]):
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
    
def get_related_memories(tx, mem_id: str, top_k: int = 5) -> list[tuple[Memory, float]]:
    query = """
    MATCH (m:Memory {id: $mem_id})-[r:RELATED_TO]-(related:Memory)
    OPTIONAL MATCH (related)-[men:MENTIONS]->(e:Entity)
    OPTIONAL MATCH (related)-[:AUTHORED_BY]->(a:Author)
    OPTIONAL MATCH (related)-[:SOURCED_FROM]->(s:Source)
    
    // sort by connection strength and return top k
    RETURN related AS node, r.connection_strength AS strength,
        [(related)-[men:MENTIONS]->(e:Entity) | {name: e.name, count: men.count}] AS entities,
        [a.name AS author | a IN collect(a)] AS authors,
        [s.name AS source | s IN collect(s)] AS sources
    ORDER BY r.connection_strength DESC
    LIMIT $top_k
    """
    result = tx.run(query, mem_id=mem_id, top_k=top_k)

    return [(record_to_memory(record), record['strength']) for record in result]


def add_memory_series(tx, memories: list[Memory]):
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
            ON CREATE SET e.mentionsCount = COALESCE(e.mentionsCount, 0) + 1
        MERGE (m)-[men:MENTIONS]->(e)
            ON CREATE SET men.isNew = true
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
    
    WITH DISTINCT m
    // connect memories in series
    WITH collect(m) AS mems
    UNWIND range(0, size(mems) - 2) AS idx
    WITH mems[idx] AS m1, mems[idx + 1] AS m2, mems
    MERGE (m1)-[r:NEXT_IN_SERIES]->(m2)
    
    WITH mems
    UNWIND mems AS m
    RETURN m.id AS mem_id   
    """
    result = tx.run(query, mem_dicts=mem_dicts)
    
    ids = [record.get('mem_id', None) for record in result]
    ids = [id for id in ids if id is not None]
    if len(ids) != len(memories):
        print(f"Warning: only {len(ids)} out of {len(memories)} memories were added successfully.")
    return ids
    
def add_memory_batch(tx, memories: list[Memory]):
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
            ON CREATE SET e.mentionsCount = COALESCE(e.mentionsCount, 0) + 1
        MERGE (m)-[men:MENTIONS]->(e)
            ON CREATE SET men.isNew = true
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
        print(f"Warning: only {len(ids)} out of {len(memories)} memories were added successfully.")
    return ids

def get_memories_by_timepoint(tx, time_point: float, window: float = 86400 * 7, top_k: int = 5):
    # get memories within time window around time_point
    # sort by closeness to time_point
    start_time = time_point - window
    end_time = time_point + window
    
    query = """
    MATCH (m:Memory)
    WHERE m.memory_time_point >= $start_time AND m.memory_time_point <= $end_time
    WITH m,
        [(m)-[men:MENTIONS]->(e_all:Entity) | {name: e_all.name, count: men.count}] AS entities,
        [(m)-[:AUTHORED_BY]->(a:Author) | a.name] AS authors,
        head([(m)-[:SOURCED_FROM]->(s:Source) | s.name]) AS source

    RETURN m AS memory, entities, authors, source
    ORDER BY abs(m.memory_time_point - $time_point) ASC
    LIMIT $top_k
    """
    result = tx.run(query, time_point=time_point, start_time=start_time, end_time=end_time, top_k=top_k)
    return [record_to_memory(record) for record in result]

def find_memories_by_entities(tx, entity_names: list[str], top_k: int = 5):
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
    result = tx.run(query, entity_names=entity_names, top_n=top_k)
    memories = {}
    for record in result:
        primary_name = record['primary_name']
        memory = record_to_memory(record)
        score = record['diversity_score']
        if primary_name not in memories:
            memories[primary_name] = []
        memories[primary_name].append((memory, score))
    return memories

def debug_compare(a, b, name="value"):
    if a != b:
        print(f"Mismatch in {name}:")
        print("A:", a)
        print("B:", b)

import random
with driver.session() as session:
    
    session.execute_write(clear_db)
    initialize_db(session)
    
    
    #for memory in memories:
    #    result = session.execute_write(add_memory, memory)
    #    print("Added memory with id:", result)

    session.execute_write(add_memory_series, memories)

    # try to find using entities
    q_entities = ["james-webb-space-telescope", "jwst", "senko-san"]
    found_memories = session.execute_read(find_memories_by_entities, q_entities, top_k=3)
    print(f"Memories found by entities {q_entities}:")
    for prim_entity, mem_list in found_memories.items():
        print(f"Primary entity: {prim_entity}")
        for mem, score in mem_list:
            print(f"- Memory ID: {mem.id}, Text: {mem.memory[:50]}..., Diversity Score: {score}")
            # give random feedback
            feedback = random.choice([FeedbackType.POSITIVE, FeedbackType.NEGATIVE, FeedbackType.NEUTRAL])
            session.execute_write(update_memory_access, [mem.id], feedback=feedback)
            
            
        

    query_memory = memories[0]
    query_embedding = embed_text(query_memory.memory).tolist()
    similar_memories = session.execute_read(find_similar_memories, query_embedding, top_k=3)
    print(f"Top similar memories to memory id {query_memory.id}:")
    for mem, sim in similar_memories:
        print(f"- Memory ID: {mem.id}, Text: {mem.memory[:50]}..., Similarity: {sim}")
        # check if all fields are the same as the original memory
        original_mem = next((m for m in memories if m.id == mem.id), None)
        assert original_mem is not None, "Memory not found in original list"
        debug_compare(mem.memory, original_mem.memory, "memory")
        debug_compare(mem.embedding.shape, original_mem.embedding.shape, "embedding shape")
        debug_compare(np.allclose(mem.embedding, original_mem.embedding), True, "embedding")
        debug_compare(mem.time_relevance, original_mem.time_relevance, "time_relevance")
        debug_compare(mem.entities, original_mem.entities, "entities")
        debug_compare(mem.memory_time_point, original_mem.memory_time_point, "memory_time_point")
        debug_compare(mem.source, original_mem.source, "source")
        debug_compare(mem.creation_time, original_mem.creation_time, "creation_time")
        # these should be different due to access update:
        #debug_compare(mem.last_access, original_mem.last_access, "last_access")
        #debug_compare(mem.total_access_count, original_mem.total_access_count, "total_access_count")
