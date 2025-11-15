# Memory Builder Module
# Used to fill graph database from various sources

from dma.core import Memory
from dma.memory import Retriever
from .wikipedia_crawler import WikipediaCrawler
from .memory_converter import BasicMemoryConverter, ArticleSplitStrategy
import tqdm

class MemoryBuilder:
    def __init__(self, retriever: Retriever, crawler: WikipediaCrawler, converter: BasicMemoryConverter):
        self.retriever = retriever
        self.crawler = crawler
        self.converter = converter
        
    def run(self, root_categories: list[str], remove_existing: bool=False) -> list[Memory]:
        if remove_existing:
            print("Removing existing memory...")
            self.retriever.graph_memory.reset_database(CONFIRM_DELETE=True)
        
        # run crawler
        articles = self.crawler.run(root_categories=root_categories, expansion_top_n_categories=0)
        
        # convert articles to memories
        memories = self.converter.convert(articles, verbose=True, split_strategy=ArticleSplitStrategy.PARAGRAPH, add_title_to_chunk=True)
        
        # add in batch to retriever
        BATCH_SIZE = 100
        print(f"Adding {len(memories)} memories to retriever in batches of {BATCH_SIZE}...")
        for i in tqdm.tqdm(range(0, len(memories), BATCH_SIZE), desc="Adding memories to retriever"):
            batch = memories[i:i+BATCH_SIZE]
            res = self.retriever.add_memory_batch(batch)
            if not res:
                print(f"Failed to add batch starting at index {i}.")
            
        print(f"Total memories added: {len(memories)}")
        return memories
    
def build_memory_of_type(memory_type: str, category: str=None, remove_existing: bool=False) -> list[Memory]:
    
    if memory_type != "wikipedia":
        print(f"Memory type '{memory_type}' is not yet implemented.")
        return []
    
    retriever = None
    try:
        retriever = Retriever()
    except Exception as e:
        print(f"Could not initialize Retriever: {e}")
        return []
    crawler = WikipediaCrawler()
    converter = BasicMemoryConverter()
    builder = MemoryBuilder(retriever, crawler, converter)
    
    categories = category.split(",") if category else []
    if len(categories) == 0:
        print("No root categories provided for Wikipedia memory build.")
        return []
    
    categories = [cat.strip() for cat in categories]
    
    memories = builder.run(root_categories=categories, remove_existing=remove_existing)
    return memories
    
    