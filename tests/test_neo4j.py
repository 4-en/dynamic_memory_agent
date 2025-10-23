# neo4j test
# tests adding Memories to Neo4j and retrieving them

from dma.core import Memory, TimeRelevance
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
    
    

memories = []
sample_texts = [
    "The James Webb Space Telescope (JWST) has a primary mirror with a diameter of 6.5 meters (21.3 feet), which gives it a collecting area of approximately 25.4 square meters. This significantly larger size compared to previous telescopes allows it to gather more light, enabling it to see objects that are older, more distant, or fainter.",
    "Unlike Hubble's single, monolithic mirror, the JWST's primary mirror is composed of 18 individual hexagonal segments. Each segment is made of beryllium, which is both strong and lightweight, and is coated with a microscopically thin layer of gold to optimize its reflectivity for infrared light. These segments had to be folded to fit inside the rocket fairing for launch and were later unfolded in space.",
    "The Hubble Space Telescope (HST) utilizes a primary mirror that is 2.4 meters (7.9 feet) in diameter, with a collecting area of about 4.5 square meters. It is a single-piece, polished glass mirror coated with layers of aluminum and magnesium fluoride. This design is optimized for observing in the near-ultraviolet, visible, and near-infrared spectra.",
    "Hubble's mirror is a monolithic structure, meaning it is made from a single piece of glass. This design choice provides high optical quality and stability, which is essential for the precise observations Hubble conducts. The mirror's surface was polished to an accuracy of about 10 nanometers, allowing it to capture sharp images of distant celestial objects."
]

test1 = "the-james-webb-space-telescope"
test2 = "james-webb-space-telescope"
test3 = "hubble-space-telescope"
test4 = "jwst"
emb1 = embed_text(test1)
emb2 = embed_text(test2)
emb3 = embed_text(test3)
emb4 = embed_text(test4)
sim = cosine_similarity(emb1, emb2)
print(f"Cosine similarity between '{test1}' and '{test2}': {sim}")
sim = cosine_similarity(emb1, emb3)
print(f"Cosine similarity between '{test1}' and '{test3}': {sim}")
sim = cosine_similarity(emb1, emb4)
print(f"Cosine similarity between '{test1}' and '{test4}': {sim}")

for i, text in enumerate(sample_texts):
    memory = Memory(
        memory=text,
        id=f"test_memory_{i}",
        time_relevance=TimeRelevance.MONTH,
        memory_time_point=time.time() - i * 86400 * 7,  # spaced a week apart
        
    )
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

def record_to_memory(record, entities: list[dict] | None = None) -> Memory:
    
    entities_dict = {}
    if entities is not None:
        for ent in entities:
            entities_dict[ent['name']] = ent['count']
    
    node = record['node']
    mem_dict = dict(node)
    mem_dict['embedding'] = np.array(mem_dict['embedding'])
    mem_dict['time_relevance'] = TimeRelevance(mem_dict['time_relevance'])
    memory = Memory(**mem_dict, entities=entities_dict)
    return memory

def add_memory(tx, memory: Memory):
    mem_id = memory.id
    mem_dict = asdict(memory)
    mem_dict['embedding'] = embed_text(memory.memory).tolist()  # convert np.ndarray to list for Neo4j storage
    mem_dict['time_relevance'] = memory.time_relevance.value  # store enum as its value
    
    query = """
    MERGE (m:Memory {id: $data.id})
    SET m.memory = $data.memory,
        m.topic = $data.topic,
        m.truthfulness = $data.truthfulness,
        m.embedding = $data.embedding,
        m.memory_time_point = $data.memory_time_point,
        m.source = $data.source,
        m.creation_time = $data.creation_time,
        m.last_access = $data.last_access,
        m.total_access_count = $data.total_access_count,
        m.time_relevance = $data.time_relevance
    RETURN m
    """
    
    # TODO: also create Entity nodes and relationships
    # also nodes and relationships for source if applicable
    
    result = tx.run(query, data=mem_dict)
    db_mem = result.single()
    
    entities_list = [ {'name': name, 'count': count} for name, count in memory.entities.items()]
    
    query = """
    // 0. increase general storage total_entity_connections
    MATCH (s:Storage {name: 'general_storage'})
    SET s.total_entity_connections = s.total_entity_connections + size($entities_list)
    
    // 1. Find or create the single Memory node
    MERGE (m:Memory {id: $mem_id})

    WITH m
    // 2. Unroll your list of entities
    UNWIND $entities_list AS entity_data

    // 3. Find or create the corresponding Entity node
    MERGE (e:Entity {name: entity_data.name})

    // 4. Find or create the relationship
    MERGE (m)-[men:MENTIONS]->(e)
        // 5. Run this ONLY IF the relationship was just CREATED
        ON CREATE
            SET e.mentionsCount = COALESCE(e.mentionsCount, 0) + 1

    // 6. Run this EVERY TIME (on create or on match)
    SET men.count = entity_data.count
    """
    tx.run(query, mem_id=mem_id, entities_list=entities_list)
    
    # add a mentioned with relationship for each entity with other entities in the memory
    query = """
    // 1. Find the memory and all entities it mentions, collecting them into a list
    MATCH (m:Memory {id: $mem_id})-[:MENTIONS]->(e:Entity)
    WITH COLLECT(e) AS entities

    // 2. Unwind the list twice to create all possible pairs
    UNWIND entities AS e1
    UNWIND entities AS e2

    // 3. Filter the pairs *before* merging
    WITH e1, e2
    WHERE e1.name < e2.name  // avoid self-relationships and duplicate pairs

    // 4. Merge the relationship and update the count
    MERGE (e1)-[r:MENTIONED_WITH]->(e2)
        ON CREATE SET r.coMentionCount = 1
        ON MATCH SET r.coMentionCount = r.coMentionCount + 1
    """
    tx.run(query, mem_id=mem_id)
    
    return db_mem

def find_similar_memories(tx, embedding: list, top_k: int = 5):
    index_name = "memory_embedding_index"
    query = """
    CALL db.index.vector.queryNodes($index_name, $top_k, $embedding)
    YIELD node, score
    WITH node, score, [(node)-[men:MENTIONS]->(e:Entity) | {name: e.name, count: men.count}] AS entities
    RETURN node, score, entities
    ORDER BY score DESC
    LIMIT $top_k
    """
    result = tx.run(query, embedding=embedding, top_k=top_k, index_name=index_name)
    return [(record_to_memory(record, entities=record['entities']), record['score']) for record in result]

def find_memory_by_id(tx, mem_id: str) -> Memory | None:
    query = """
    MATCH (m:Memory {id: $mem_id})
    OPTIONAL MATCH (m)-[men:MENTIONS]->(e:Entity)
    RETURN m AS node, [(m)-[men:MENTIONS]->(e:Entity) | {name: e.name, count: men.count}] AS entities
    """
    result = tx.run(query, mem_id=mem_id)
    record = result.single()
    if record is None:
        return None
    return record_to_memory(record, entities=record['entities'])

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
        [(m)-[men:MENTIONS]->(e_all:Entity) | {name: e_all.name, count: men.count}] AS mentions
        
    RETURN primary_name, m AS node, diversity_score, mentions
    """
    result = tx.run(query, entity_names=entity_names, top_n=top_k)
    memories = {}
    for record in result:
        primary_name = record['primary_name']
        memory = record_to_memory(record, entities=record['mentions'])
        score = record['diversity_score']
        if primary_name not in memories:
            memories[primary_name] = []
        memories[primary_name].append((memory, score))
    return memories

def debug_compare(a, b):
    if a != b:
        print("Values differ:")
        print("A:", a)
        print("B:", b)


with driver.session() as session:
    
    session.execute_write(clear_db)
    initialize_db(session)
    
    
    for memory in memories:
        result = session.execute_write(add_memory, memory)
        print("Added memory with id:", result['m']['id'])
        
    # try to find using entities
    q_entities = ["james-webb-space-telescope", "jwst", "senko-san"]
    found_memories = session.execute_read(find_memories_by_entities, q_entities, top_k=3)
    print(f"Memories found by entities {q_entities}:")
    for prim_entity, mem_list in found_memories.items():
        print(f"Primary entity: {prim_entity}")
        for mem, score in mem_list:
            print(f"- Memory ID: {mem.id}, Text: {mem.memory[:50]}..., Diversity Score: {score}")
        

    query_memory = memories[0]
    query_embedding = embed_text(query_memory.memory).tolist()
    similar_memories = session.execute_read(find_similar_memories, query_embedding, top_k=3)
    print(f"Top similar memories to memory id {query_memory.id}:")
    for mem, sim in similar_memories:
        print(f"- Memory ID: {mem.id}, Text: {mem.memory[:50]}..., Similarity: {sim}")
        # check if all fields are the same as the original memory
        original_mem = next((m for m in memories if m.id == mem.id), None)
        assert original_mem is not None, "Memory not found in original list"
        debug_compare(mem.memory, original_mem.memory)
        debug_compare(mem.embedding.shape, original_mem.embedding.shape)
        debug_compare(np.allclose(mem.embedding, original_mem.embedding), True)
        debug_compare(mem.time_relevance, original_mem.time_relevance)
        debug_compare(mem.entities, original_mem.entities)
        debug_compare(mem.memory_time_point, original_mem.memory_time_point)
        debug_compare(mem.source, original_mem.source)
        debug_compare(mem.creation_time, original_mem.creation_time)
        debug_compare(mem.last_access, original_mem.last_access)
        debug_compare(mem.total_access_count, original_mem.total_access_count)
        