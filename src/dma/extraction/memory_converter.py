# converts articles to memories

from dma.core import WebSourceData, Memory, Source
from dma.utils import NER, get_cache_dir
import tqdm
from pathlib import Path
import os
import urllib.parse
import json

from abc import ABC, abstractmethod
from enum import Enum

class MemoryConverter(ABC):
    @abstractmethod
    def convert(self, articles: list[WebSourceData], verbose: bool=True, **kwargs) -> list[Memory]:
        pass
    
    
class ArticleSplitStrategy(Enum):
    NONE = 0 # no splitting, use full article
    SENTENCE = 1 # split by sentence
    LINE = 2 # split by line (newline)
    PARAGRAPH = 3 # split by paragraph (double newline)
    HEADING = 4 # split by headings (not implemented yet)

class BasicMemoryConverter(MemoryConverter):
    """
    A basic implementation of MemoryConverter that converts WebSourceData articles into Memory objects.
    
    Converts article into memories using a basic strategy.
    """
    
    def __init__(self):
        super().__init__()
        self.cache_dir = get_cache_dir() / "basic_memory_converter"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _split_by_heading_heuristic(self, full_text):
        sections = {} # Use a dictionary to store sections by name
        current_heading = "Introduction" # Default for text before first heading
        current_content = []

        # 1. Split by the "paragraph" (double newline)
        blocks = full_text.split('\n\n')

        for block in blocks:
            if not block.strip():
                continue # Skip empty lines

            # 2. Get the first line of the block
            lines = block.split('\n')
            first_line = lines[0]

            # 3. Apply the heuristic
            is_heading = (
                len(first_line.split()) < 10 and  # It's short (fewer than 10 words)
                not first_line.endswith('.') and  # Doesn't end with a period
                len(first_line) < 80              # It's short (fewer than 80 chars)
            )

            if is_heading:
                # 4. Save the previous section
                if current_content:
                    sections[current_heading] = '\n\n'.join(current_content)
                
                # 5. Start the new section
                current_heading = first_line
                # Add the rest of the block (if any) to the new section's content
                remaining_content = '\n'.join(lines[1:])
                if remaining_content:
                    current_content = [remaining_content]
                else:
                    current_content = []
            else:
                # 4. Not a heading, so just add this block to the current section
                current_content.append(block)

        # 6. Add the very last section
        if current_content:
            sections[current_heading] = '\n\n'.join(current_content)

        return sections
    
    def _split_text(self, text: str, strategy: ArticleSplitStrategy) -> list[str]:
        if strategy == ArticleSplitStrategy.NONE:
            return [text]
        elif strategy == ArticleSplitStrategy.SENTENCE:
            eos = {'.', '!', '?'}
            sentences = []
            current_sentence = []
            for char in text:
                current_sentence.append(char)
                if char in eos:
                    sentences.append(''.join(current_sentence).strip())
                    current_sentence = []
            if current_sentence:
                sentences.append(''.join(current_sentence).strip())
            return sentences
        elif strategy == ArticleSplitStrategy.LINE:
            return [line.strip() for line in text.split('\n') if line.strip()]
        elif strategy == ArticleSplitStrategy.PARAGRAPH:
            return [para.strip() for para in text.split('\n\n') if para.strip()]
        elif strategy == ArticleSplitStrategy.HEADING:
            sections = self._split_by_heading_heuristic(text)
            return [content.strip() for content in sections.values() if content.strip()]
        else:
            raise ValueError(f"Unknown split strategy: {strategy}")
        
    def _filter_chunks(self, chunks: list[str], min_length: int = 20) -> list[str]:
        ignored_headings = {"See also", "References", "External links", "Further reading", "Sources", "Notes"}
        filtered = []
        for chunk in chunks:
            if any(chunk.startswith(heading) for heading in ignored_headings):
                continue
            if len(chunk) < min_length:
                continue
            filtered.append(chunk)
        return filtered
    
    def _get_memory_cache_path(self, article: WebSourceData) -> Path:
        safe_title = urllib.parse.quote_plus(article.title)
        return self.cache_dir / f"{safe_title}.json"
    
    def _get_cached_memories(self, article: WebSourceData) -> list[Memory] | None:
        cache_path = self._get_memory_cache_path(article)
        if cache_path and cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                memories = []
                for mem_data in data.get("memories", []):
                    mem = Memory.from_dict(mem_data)
                    memories.append(mem)
                return memories
            except Exception as e:
                print(f"Error loading cached memories for article '{article.title}': {e}")
                return None
        return None
    
    def _cache_memories(self, article: WebSourceData, memories: list[Memory]) -> None:
        cache_path = self._get_memory_cache_path(article)
        if not cache_path:
            return
        try:
            data = {
                "memories": [mem.to_dict() for mem in memories]
            }
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error caching memories for article '{article.title}': {e}")

    def convert(self, articles: list[WebSourceData], verbose: bool=True, split_strategy: ArticleSplitStrategy=ArticleSplitStrategy.NONE, add_title_to_chunk: bool=False, **kwargs) -> list[Memory]:
        memories = []
        name_to_src = {}
        # fill name_to_src map
        for article in articles:
            if article.url and article.title:
                name_to_src[article.title] = Source.from_web(article.url)
                
        # load cached file names for faster lookup
        cached_files = set(os.listdir(self.cache_dir)) if self.cache_dir.exists() else set()
        

        iterator = tqdm.tqdm(articles, desc="Converting articles to memories") if verbose else articles
        for article in iterator:
            
            # try using cached version of article if available
            if article.title:
                safe_title = urllib.parse.quote_plus(article.title)
                cache_filename = f"{safe_title}.json"
                if cache_filename in cached_files:
                    cached_memories = self._get_cached_memories(article)
                    if cached_memories is not None:
                        memories.extend(cached_memories)
                        continue
            
            source = Source.from_web(article.url)
            # categories = article.categories if article.categories else []
            # removed category extraction for now, since they contain too
            # many non-useful categories and meta categories, which add unwanted noise
            # and bloat the entity connections
            # we can re-add this later with a better mechanism for filtering useful categories
            categories = []
            categories.append(article.title)
            # clean categories to be just the title strings
            for i in range(len(categories)):
                if isinstance(categories[i], str):
                    categories[i] = categories[i].replace("Category:", "").strip()
                    categories[i] = categories[i].replace("Category/", "").strip()
                    categories[i] = NER.normalize_entity(categories[i])
                    
            references = article.links_to if article.links_to else []
            # convert references to Source objects
            reference_sources = []
            for ref in references:
                src = name_to_src.get(ref, None)
                if src:
                    reference_sources.append(src)
                    
            text_chunks = self._split_text(article.content_plaintext, split_strategy)
            text_chunks = self._filter_chunks(text_chunks)
            
            cache_candidates = []
            
            for chunk in text_chunks:
                if add_title_to_chunk:
                    chunk = f"{article.title}\n\n{chunk}"
                new_memory = Memory(
                    memory=chunk,
                    source=source,
                    references=reference_sources,
                    topic=article.title
                )
                
                for category in categories:
                    if not category in new_memory.entities:
                        new_memory.entities[category] = 0.0
                    new_memory.entities[category] += 1.0

                memories.append(new_memory)
                cache_candidates.append(new_memory)

            if article.title and cache_candidates:
                self._cache_memories(article, cache_candidates)

        return memories