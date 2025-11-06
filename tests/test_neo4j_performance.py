from dma.memory.graph import Neo4jMemory
from time import time

def print_results(results):
    print(f"Unique entities found: {len(results)}")
    total_memories = sum(len(graph_results) for graph_results in results.values())
    print(f"Total memories retrieved: {total_memories}")
    print("Detailed Results:")
    
    for entity, graph_results in results.items():
        print(f"Entity: {entity}")
        for i, mem_res in enumerate(graph_results):
            print(f"  Memory {i} (ID: {mem_res.memory.id}, score: {mem_res.score}) has {len(mem_res.memory.entities)} entities.")

def benchmark(fn, *args, **kwargs):
    start_time = time()
    result = fn(*args, **kwargs)
    end_time = time()
    print(f"Function {fn.__name__} took {end_time - start_time:.6f} seconds")
    return result

print("Loading Neo4jMemory...")
memory = Neo4jMemory()

print("Benchmarking query_memories_by_entities...")
res = benchmark(memory.query_memories_by_entities, entities=["earth", "mars"], limit=10)
print_results(res)

# print the first memories content
if res:
    first_memory = next(iter(res.values())).pop(0)
    print(f"First memory content (ID: {first_memory.memory.id}):")
    print(f"  Text: {first_memory.memory.memory}")
    print(f"  Entities: {first_memory.memory.entities}")
    print(f"  Authors: {first_memory.memory.source.authors}")
    print(f"  Publisher: {first_memory.memory.source.publisher}")