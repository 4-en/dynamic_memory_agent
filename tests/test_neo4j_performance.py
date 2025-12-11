from dma.memory.graph import Neo4jMemory
from time import time
import numpy as np

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

def calc_top_percentile(times, percentile=90):
    sorted_times = sorted(times)
    index = int(len(sorted_times) * (percentile / 100))
    return sorted_times[index - 1]

print("Loading Neo4jMemory...")
memory = Neo4jMemory()

# benchmark random vector search
DIM = 384
N_QUERIES = 1000
random_vectors = np.random.rand(N_QUERIES, DIM).tolist()
times = []
entities = set()
for vec in random_vectors:
    start = time()
    res = memory.query_memories_by_vector(vector=vec, top_k=10)
    end = time()
    times.append(end - start)
    for mem_res in res:
        for entity in mem_res.memory.entities.keys():
            entities.add(entity)
            
top_90 = calc_top_percentile(times, 90)
top_95 = calc_top_percentile(times, 95)
mean_time = sum(times) / len(times)

print(f"Random Vector Search Benchmark Results:")
print(f"Total queries: {N_QUERIES}")
print(f"Top 90th percentile time: {top_90:.6f} seconds")
print(f"Top 95th percentile time: {top_95:.6f} seconds")
print(f"Mean time: {mean_time:.6f} seconds")
print()

# benchmark query by entities
import random
ENTITIES_PER_QUERY = 10
entities_list = list(entities)
times = []
for i in range(N_QUERIES):
    # randomly select entities for the query
    selected_entities = random.choices(entities_list, k=ENTITIES_PER_QUERY)
    start = time()
    res = memory.query_memories_by_entities(entities=selected_entities, limit=10)
    end = time()
    times.append(end - start)
    
top_90 = calc_top_percentile(times, 90)
top_95 = calc_top_percentile(times, 95)
mean_time = sum(times) / len(times)
print(f"Entity-Based Search Benchmark Results:")
print(f"Total queries: {N_QUERIES}")
print(f"Top 90th percentile time: {top_90:.6f} seconds")
print(f"Top 95th percentile time: {top_95:.6f} seconds")
print(f"Mean time: {mean_time:.6f} seconds")
print()



# compare old vs new entity query performance
old_fn = memory._query_memories_by_entities
new_fn = memory._query_memories_by_entities2
N_COMPARISON_QUERIES = 10 # only ten, since old method is very slow
old_times = []
new_times = []
for i in range(N_COMPARISON_QUERIES):
    selected_entities = random.choices(entities_list, k=ENTITIES_PER_QUERY)
    
    memory._query_memories_by_entities2 = old_fn
    start = time()
    old_res = memory.query_memories_by_entities(entities=selected_entities, limit=10)
    end = time()
    old_times.append(end - start)
    
    memory._query_memories_by_entities2 = new_fn
    start = time()
    new_res = memory.query_memories_by_entities(entities=selected_entities, limit=10)
    end = time()
    new_times.append(end - start)
    
mean_old_time = sum(old_times) / len(old_times)
mean_new_time = sum(new_times) / len(new_times)
print(f"Old vs New Entity Query Performance:")
print(f"Mean time old method: {mean_old_time:.6f} seconds")
print(f"Mean time new method: {mean_new_time:.6f} seconds")
print()


print("Benchmarking query_memories_by_entities...")
res = benchmark(memory.query_memories_by_entities, entities=["earth", "mars"], limit=10)
# print_results(res)

# print the first memories content
if res:
    first_memory = next(iter(res.values())).pop(0)
    print(f"First memory content (ID: {first_memory.memory.id}):")
    print(f"  Text: {first_memory.memory.memory}")
    print(f"  Entities: {first_memory.memory.entities}")
    print(f"  Authors: {first_memory.memory.source.authors}")
    print(f"  Publisher: {first_memory.memory.source.publisher}")