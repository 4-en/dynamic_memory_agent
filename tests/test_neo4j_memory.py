from dma.memory.graph import Neo4jMemory
from dma.core import Memory, TimeRelevance, Source, FeedbackType, MemoryFeedback
import time
import random
import logging

logging.basicConfig(level=logging.INFO)

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

res = db.reset_database(CONFIRM_DELETE=True)
assert_verbose(database_reset=res)

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

    memory.references = [Source.from_web(f"https://example.com/article_{i}", authors=[f"Author {i}"], publisher="Example Publisher")]

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

# test query by entities
query_entities = ["senko-san", "yuzu"]
entity_query_results = db.query_memories_by_entities(query_entities, limit=3)
for entity in query_entities:
    results = entity_query_results.get(entity, [])
    for gr in results:
        assert_verbose(entity_in_memory=entity in gr.memory.entities)
        
# test query by vector
test_vector = memories[0].embedding
vector_query_results = db.query_memories_by_vector(test_vector, top_k=3)
assert_verbose(vector_query_size=len(vector_query_results), expected_size=3)
# first result should be the memory itself
assert_verbose(top_vector_match_id=vector_query_results[0].memory.id, expected_id=memories[0].id)

# test connecting memories to each other
res = db.connect_memories([memory_sequence[0].id, memory_sequence[1].id])
assert_verbose(connected_memory_ids=res)

# test getting related memories
related_memories = db.query_related_memories(memory_sequence[0].id, top_k=2)
assert_verbose(related_size=len(related_memories), expected_size=1)  # only one related memory in this case
assert_verbose(related_memory_id=related_memories[0].memory.id, expected_id=memory_sequence[1].id)

# test updating memory access
res = db.update_memory_access([memory_sequence[0].id], FeedbackType.POSITIVE)
assert_verbose(updated_memory_ids=res, expected_ids=[memory_sequence[0].id])
updated_memory = db.query_memory_by_id(memory_sequence[0].id)
timestamp_increased = updated_memory.last_access > memory_sequence[0].last_access
assert_verbose(timestamp_increased=timestamp_increased)
access_count_increased = updated_memory.total_access_count == (memory_sequence[0].total_access_count + 1)
assert_verbose(access_count_increased=access_count_increased)
positive_feedback_increased = updated_memory.positive_access_count == (memory_sequence[0].positive_access_count + 1)
assert_verbose(positive_feedback_increased=positive_feedback_increased)

# test querying memory series
series_memories = db.query_memory_series(memory_sequence[2].id, previous=4, next=2)
expected_series_size = 5  # 2 previous (4 given, but only 2 prev in series) + 1 origin + 2 next
assert_verbose(series_size=len(series_memories), expected_size=expected_series_size)
expected_ids = {memory_sequence[0].id, memory_sequence[1].id, memory_sequence[2].id, memory_sequence[3].id, memory_sequence[4].id}
retrieved_ids = {mem.id for mem in series_memories}
assert_verbose(series_ids_match=retrieved_ids == expected_ids)

# test deep relationship traversal
res = db.deep_relationship_traversal("test_memory_3", max_depth=3, stop_k=10)
assert_verbose(traversal_results=len(res), expected_n=2)  # should find two related memories
# one should be 2 away (score 1/2), one should be 3 away (score 1/3)
expected_scores = {1/2, 1/3}
retrieved_scores = {gr.score for gr in res}
assert_verbose(traversal_scores_match=retrieved_scores == expected_scores)

# test updating memory weights
feedbacks = [
    MemoryFeedback(memory_id=memory_sequence[0].id, feedback=FeedbackType.POSITIVE, entities=["senko-san", "TEST_A"]),
    MemoryFeedback(memory_id=memory_sequence[1].id, feedback=FeedbackType.NEGATIVE, entities=["senko-san", "TEST_B"]),
    MemoryFeedback(memory_id=memory_sequence[2].id, feedback=FeedbackType.POSITIVE, entities=["senko-san", "TEST_C"]),
    MemoryFeedback(memory_id=memory_sequence[3].id, feedback=FeedbackType.NEUTRAL, entities=["yuzu", "TEST_D"])
]
res = db.update_memory_weights(feedbacks)
assert_verbose(weights_updated=res)

print("All tests passed successfully.")