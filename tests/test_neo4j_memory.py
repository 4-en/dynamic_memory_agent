from dma.memory.graph import Neo4jMemory
from dma.core import Memory, TimeRelevance, Source
import time
import random

db = Neo4jMemory()

assert db.is_connected()

db.reset_database(CONFIRM_DELETE=True)

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
    
# set single add memory
res = db.add_memory(memories[0])
assert res is True
print("Added single memory.")

# set add memory batch
res_ids = db.add_memory_batch(memories[1:])
assert len(res_ids) == len(memories) - 1
print("Added memory batch.")

# test query by ids
query_ids = [memories[0].id, memories[2].id]
queried_memories = db.query_memories_by_id(query_ids)
assert len(queried_memories) == 2
for qm in queried_memories:
    original_mem = next((m for m in memories if m.id == qm.id), None)
    assert original_mem is not None
    assert qm.memory == original_mem.memory
print("Queried memories by IDs successfully.")

memory_sequence = []
random.seed(42)  # For reproducibility
entities_pool = ["senko-san", "ahri", "yuzu", "fubuki"]
for i in range(6):
    mem = Memory(
        memory=f"Sequential memory {i}",
        id=f"seq_memory_{i}",
        time_relevance=TimeRelevance.DAY,
        memory_time_point=time.time() - i * 3600,  # spaced an hour apart
        entities={entity: 1 for entity in random.sample(entities_pool, k=2)}
    )
    memory_sequence.append(mem)
    
res = db.add_memory_series(memory_sequence)
assert res is True
print("Added memory series successfully.")


