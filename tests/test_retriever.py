from dma.memory import Retriever
from dma.core import Memory, MemoryResult, EntityQuery, EmbeddingQuery, Retrieval, RetrievalQuery, RetrievalStep, Message, Conversation, Role

import time
import numpy as np
import random


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

print("Loading Retriever...")
retriever = Retriever()
# initial memories
DIM = 384
N_MEM = 100

random.seed(42)
np.random.seed(42)

conversation = Conversation()
conversation.add_message(Message(role=Role.USER, content="Test retrieval")) 

vectors = np.random.rand(N_MEM, DIM).tolist()
memories = []
for i in range(N_MEM):
    res = retriever.graph_memory.query_memories_by_vector(vector=vectors[i], top_k=1)
    if res:
        memories.append(res[0].memory)
        
# benchmark retriever
# N_QUERIES = 1000
# times = []
# for i in range(N_QUERIES):
#     memory_sample = random.sample(memories, k=5)
#     retrieval_step = RetrievalStep()
#     for mem in memory_sample:
#         retrieval_step.queries.append(RetrievalQuery(
#             entity_queries=[EntityQuery(entity=ent) for ent in mem.entities.keys()],
#             embedding_query=EmbeddingQuery.from_text(mem.memory)
#         ))
#     start = time.time()
#     res = retriever.retrieve(conversation=conversation, query=retrieval_step, top_k=10)
#     end = time.time()
#     times.append(end - start)
    
# top_90 = calc_top_percentile(times, 90)
# top_95 = calc_top_percentile(times, 95)
# mean_time = sum(times) / len(times)
# print(f"Retriever Benchmark Results:")
# print(f"Total queries: {N_QUERIES}")
# print(f"Top 90th percentile time: {top_90:.6f} seconds")
# print(f"Top 95th percentile time: {top_95:.6f} seconds")
# print(f"Mean time: {mean_time:.6f} seconds")
# print()
       
       
# test retiever accuracy        
# create queries using memories
retrieval_step = RetrievalStep()
for mem in memories[:5]:
    retrieval_step.queries.append(RetrievalQuery(
        # use half the entities for the query to approximate real world scenario
        entity_queries=[EntityQuery(entity=ent) for ent in random.sample(list(mem.entities.keys()), k=len(mem.entities)//2)],
        embedding_query=EmbeddingQuery.from_text(mem.memory)
    ))
    retrieval_step.queries[-1].embedding_query.embedding+= np.random.normal(0, 0.1, DIM)  # add slight noise to embedding
   

    
res = retriever.retrieve(conversation=conversation, query=retrieval_step, top_k=10)

print("Target IDs:")
for mem in memories[:5]:
    print(f"- {mem.id}")
    
print("\nRetrieved Memories:")
for r in res:
    print(f"- ID: {r.memory.id}, Score: {r.score}, In Targets: {r.memory.id in [m.id for m in memories]}")
    

