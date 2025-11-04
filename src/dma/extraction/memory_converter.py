# converts articles to memories

from dma.core import WebSourceData, Memory, Source
from dma.utils import NER
import tqdm

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

    def convert(self, articles: list[WebSourceData], verbose: bool=True, split_strategy: ArticleSplitStrategy=ArticleSplitStrategy.NONE, add_title_to_chunk: bool=False, **kwargs) -> list[Memory]:
        memories = []
        name_to_src = {}
        # fill name_to_src map
        for article in articles:
            if article.url and article.title:
                name_to_src[article.title] = Source.from_web(article.url)
            

        iterator = tqdm.tqdm(articles, desc="Converting articles to memories") if verbose else articles
        for article in iterator:
            source = Source.from_web(article.url)
            categories = article.categories if article.categories else []
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

        return memories