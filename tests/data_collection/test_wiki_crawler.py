from dma.extraction import WikipediaCrawler

import time

base_categories = ["Solar System"]
crawler = WikipediaCrawler(manual_category_confirmation=True)
start_time = time.time()
data = crawler.run(
    root_categories=base_categories,
    max_depth=2,
    expansion_top_n_links="EQUAL",
    expansion_top_n_categories=0
)
end_time = time.time()
print(f"Crawl completed in {end_time - start_time} seconds")
print(f"Number of articles retrieved: {len(data)}")

# sample output of first 3 articles
print("\nSample Articles:")
for article in data[:3]:
    print(f"Title: {article.title}")
    print(f"URL: {article.url}")
    print(f"Page ID: {article.pageid}")
    print(f"Last Updated: {article.last_updated}")
    print(f"Summary: {article.summary[:100]}...")  # Print first 100 chars of summary
    print(f"Categories: {article.categories}")
    print(f"Links To: {article.links_to[:5]}...")  # Print first 5 links
    print("-----")
    
from dma.extraction import BasicMemoryConverter, ArticleSplitStrategy

converter = BasicMemoryConverter()
memories = converter.convert(
    articles=data,
    verbose=True,
    split_strategy=ArticleSplitStrategy.PARAGRAPH,
    add_title_to_chunk=True
)

print(f"\nNumber of memory chunks created: {len(memories)}")
# sample output of first 3 memory chunks
print("\nSample Memory Chunks:")
for memory in memories[:3]:
    print(f"Memory Chunk: {memory.memory[:100]}...")  # Print first 100 chars of memory
    print(f"Source URL: {memory.source.source}")
    print(f"Topic: {memory.topic}")
    print(f"Entities: {memory.entities}")
    print("-----")