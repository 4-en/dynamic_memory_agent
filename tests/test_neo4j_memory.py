from dma.memory.graph import Neo4jMemory
from dma.core import Memory, TimeRelevance, Source
import time
import random

def assert_verbose(**kwargs):
    # Simple helper function to assert with verbose output
    # compares passed keyword arguments for equality
    if len(kwargs) < 1:
        raise ValueError("At least one keyword argument is required for comparison.")
    elif len(kwargs) == 1:
        # assume we want to assert it's not None
        key, value = next(iter(kwargs.items()))
        assert value is not None, f"Assertion failed: {key} is None"
        return
    items = list(kwargs.items())
    first_key, first_value = items[0]
    for key, value in items[1:]:
        assert first_value == value, f"Assertion failed: {first_key} != {key} ({first_value} != {value})"

db = Neo4jMemory()

assert_verbose(connected=db.is_connected())

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
    
    memories.append(memory)
    
# set single add memory
res = db.add_memory(memories[0])
assert_verbose(added_single_memory=res)

# set add memory batch
res_ids = db.add_memory_batch(memories[1:])
assert_verbose(batch_size=len(memories)-1, returned_ids=len(res_ids))

# test query by ids
query_ids = [memories[0].id, memories[2].id]
queried_memories = db.query_memories_by_id(query_ids)
assert_verbose(queried_size=len(queried_memories), expected_size=len(query_ids))
for qm in queried_memories:
    original_mem = next((m for m in memories if m.id == qm.id), None)
    assert_verbose(found_original=original_mem)
    assert_verbose(queried_memory=qm.memory, original_memory=original_mem.memory)

# test add memory series
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
assert_verbose(added_memory_series=res)


print("All tests passed successfully.")