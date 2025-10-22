# neo4j test
# tests adding Memories to Neo4j and retrieving them

from dma.core import Memory, TimeRelevance
from dma.utils import embed_text
from dataclasses import asdict
import time
from neo4j import GraphDatabase
import json

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
    

def add_memory(tx, memory: Memory):
    mem_id = memory.id
    mem_dict = asdict(memory)
    mem_dict['embedding'] = embed_text(memory.memory).flatten().tolist()  # convert np.ndarray to list for Neo4j storage
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

with driver.session() as session:
    session.execute_write(initialize_db)
    for memory in memories:
        result = session.execute_write(add_memory, memory)
        print("Added memory with id:", result['m']['id'])
    
    