# utility functions for working with sources

from enum import Enum
from dataclasses import dataclass, field

class SourceType(Enum):
    WEB = "web"
    BOOK = "book"
    ARTICLE = "article"
    OTHER = "other"
    
@dataclass
class Source:
    source_type: SourceType = SourceType.OTHER
    full_source: str = None
    source: str = None
    authors: list[str] = field(default_factory=list)
    publisher: str = None
    
    def __post_init__(self):
        # normalize authors
        self.authors = Source.normalize_authors(self.authors)
        # normalize source
        self.source = Source.normalize_source(self.source)
        # normalize publisher
        self.publisher = Source.normalize_source(self.publisher)
    
    @staticmethod
    def normalize_authors(authors: list[str]) -> list[str]:
        if not authors:
            return []
        cleaned_authors = []
        for author in authors:
            author = author.strip()
            author = author.lower()
            author = "-".join(author.split())  # remove extra spaces
            if author:
                cleaned_authors.append(author)
                
        # sort authors for consistency
        cleaned_authors = sorted(list(set(cleaned_authors)))
        return cleaned_authors
    
    @staticmethod
    def normalize_source(source: str) -> str:
        if not source:
            return None
        source = source.strip().lower()
        return source
    
    @staticmethod
    def from_web(url: str, authors: list[str] = None, publisher: str = None) -> 'Source':
        # clean url to remove protocol, www and non-essential parts
        url = url.split("://")[-1]
        url = url.replace("www.", "")
        # remove url parameters
        url = url.split("?")[0]
        # remove sections #
        url = url.split("#")[0]

        url = url.strip().lower()
        
        # if publisher is None, use domain as publisher
        if not publisher:
            publisher = url.split("/")[0]
        publisher = Source.normalize_source(publisher)
        
        
        return Source(
            source_type=SourceType.WEB, 
            full_source=url, 
            source=url, 
            authors=Source.normalize_authors(authors),
            publisher=publisher
        )

    @staticmethod
    def from_book(title: str, authors: list[str] = None, year: int=None, publisher: str = None) -> 'Source':
        book_source = title
        source = book_source
        authors = Source.normalize_authors(authors)
        if authors:
            book_source += f" by {', '.join(authors)}"
            source = book_source
        if year:
            book_source += f" ({year})"
        if publisher:
            publisher = Source.normalize_source(publisher)
        source = Source.normalize_source(source)
        return Source(
            source_type=SourceType.BOOK,
            full_source=book_source,
            source=source,
            authors=authors,
            publisher=publisher
        )

    @staticmethod
    def from_article(title: str, authors: list[str] = None, journal: str = None, year: int=None) -> 'Source':
        article_source = title
        source = article_source
        authors = Source.normalize_authors(authors)
        if authors:
            article_source += f" by {', '.join(authors)}"
            source = article_source
        if journal:
            article_source += f", published in {journal}"
        if year:
            article_source += f" ({year})"
        source = Source.normalize_source(source)
        return Source(
            source_type=SourceType.ARTICLE,
            full_source=article_source,
            source=source,
            authors=authors,
            publisher=Source.normalize_source(journal)
        )
        
    @staticmethod
    def from_other(source: str, authors: list[str] = None, publisher: str = None) -> 'Source':
        if not authors:
            authors = []
        authors = Source.normalize_authors(authors)
        return Source(
            source_type=SourceType.OTHER,
            full_source=source,
            source=Source.normalize_source(source),
            authors=authors,
            publisher=Source.normalize_source(publisher) if publisher else None
        )
        
    @staticmethod
    def from_string(source_str: str) -> 'Source':
        # try to infer source type from string
        # if it looks like a url, use WEB
        # otherwise use OTHER
        is_web = False
        if (source_str.startswith("http://") or 
            source_str.startswith("https://") or 
            source_str.startswith("www.")):
            is_web = True
            
        if not is_web:
            # check for patterns of [something].[something]
            dot_pos = source_str.find(".")
            if dot_pos > 1 and dot_pos < len(source_str) - 1:
                char_before = source_str[dot_pos - 1]
                char_after = source_str[dot_pos + 1]
                if (char_before.isalnum() and char_after.isalnum()):
                    is_web = True
                    
        if is_web:
            return Source.from_web(source_str)
        else:
            return Source.from_other(source_str)


    @staticmethod
    def unknown() -> 'Source':
        return Source(
            source_type=SourceType.OTHER,
            full_source=None,
            source=None,
            authors=[],
            publisher=None
        )
        
    @staticmethod
    def from_source_type(source_type: SourceType, full_source: str = None, source: str = None, authors: list[str] = None, publisher: str = None) -> 'Source':
        if source_type == SourceType.WEB:
            return Source.from_web(full_source if full_source else source, authors, publisher)
        elif source_type == SourceType.BOOK:
            return Source.from_book(full_source if full_source else source, authors, publisher=publisher)
        elif source_type == SourceType.ARTICLE:
            return Source.from_article(full_source if full_source else source, authors, journal=publisher)
        else:
            return Source.from_other(full_source if full_source else source, authors, publisher)
        
    def __eq__(self, other):
        if not isinstance(other, Source):
            return False
        return (self.source_type == other.source_type and
                self.full_source == other.full_source and
                self.source == other.source and
                self.authors == other.authors and
                self.publisher == other.publisher)
        
    def equals_source(self, other: 'Source') -> bool:
        """Only compares the source string.

        Parameters
        ----------
        other : Source
            The other source to compare.
            
        Returns
        -------
        bool
            True if the sources are the same, False otherwise.
        """
        if not isinstance(other, Source):
            return False
        return (self.source == other.source)
    
    def __hash__(self):
        if self.source:
            return hash(self.source)
        return hash((self.source_type, self.full_source, tuple(self.authors), self.publisher))