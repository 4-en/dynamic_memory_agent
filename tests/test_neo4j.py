# neo4j test
# tests adding Memories to Neo4j and retrieving them

from dma.core import Memory, TimeRelevance
from dma.utils import embed_text
from dataclasses import asdict
import time
from neo4j import GraphDatabase
import json
import numpy as np

def initialize_db(tx):
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
    }}
    """)
    
    

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
    mem_dict = dict(node)
    mem_dict['embedding'] = np.array(mem_dict['embedding'])
    mem_dict['entities'] = json.loads(mem_dict['entities'])
    mem_dict['time_relevance'] = TimeRelevance(mem_dict['time_relevance'])
    memory = Memory(**mem_dict)
    return memory

def add_memory(tx, memory: Memory):
    mem_id = memory.id
    mem_dict = asdict(memory)
    mem_dict['embedding'] = embed_text(memory.memory).tolist()  # convert np.ndarray to list for Neo4j storage
    mem_dict['entities'] = json.dumps(memory.entities)  # store entities dict as JSON string
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
        m.time_relevance = $data.time_relevance,
        m.entities = $data.entities
    RETURN m
    """
    
    # TODO: also create Entity nodes and relationships
    # also nodes and relationships for source if applicable
    
    result = tx.run(query, data=mem_dict)
    return result.single()

def find_similar_memories(tx, embedding: list, top_k: int = 5):
    index_name = "memory_embedding_index"
    query = f"""
    CALL db.index.vector.queryNodes($index_name, $top_k, $embedding)
    YIELD node, score
    RETURN node, score
    ORDER BY score DESC
    LIMIT $top_k
    """
    result = tx.run(query, embedding=embedding, top_k=top_k, index_name=index_name)
    return [(record_to_memory(record), record['score']) for record in result]

def debug_compare(a, b):
    if a != b:
        print("Values differ:")
        print("A:", a)
        print("B:", b)


with driver.session() as session:
    session.execute_write(initialize_db)
    
    # wipe the database for testing
    session.execute_write(clear_db)
    
    for memory in memories:
        result = session.execute_write(add_memory, memory)
        print("Added memory with id:", result['m']['id'])
        
    
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
        