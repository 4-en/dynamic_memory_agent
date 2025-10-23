# utility functions for working with sources

from enum import Enum
from dataclasses import dataclass

class SourceType(Enum):
    WEB = "web"
    BOOK = "book"
    ARTICLE = "article"
    VIDEO = "video"
    PODCAST = "podcast"
    OTHER = "other"
    
@dataclass
class Source:
    source_type: SourceType = SourceType.OTHER
    full_source: str = ""
    source: str = ""
    
    @staticmethod
    def from_web(url: str) -> 'Source':
        # clean url to remove protocol, www and non-essential parts
        url = url.split("://")[-1]
        url = url.replace("www.", "")
        # remove url parameters
        url = url.split("?")[0]
        # remove sections #
        url = url.split("#")[0]

        url = url.strip().lower()
        return Source(source_type=SourceType.WEB, full_source=url, source=url)

    @staticmethod
    def from_book(title: str, author: str=None, year: int=None) -> 'Source':
        book_source = title
        if author:
            book_source += f" by {author}"
        if year:
            book_source += f" ({year})"
        return Source(source_type=SourceType.BOOK, full_source=book_source, source=book_source.lower())

    @staticmethod
    def from_article(title: str, publication: str=None, date: str=None) -> 'Source':
        article_source = title
        if publication:
            article_source += f", {publication}"
        if date:
            article_source += f" ({date})"
        return Source(source_type=SourceType.ARTICLE, full_source=article_source, source=article_source.lower())
    
    @staticmethod
    def from_video(title: str, creator: str=None, year: int=None) -> 'Source':
        video_source = title
        if creator:
            video_source += f" by {creator}"
        if year:
            video_source += f" ({year})"
        return Source(source_type=SourceType.VIDEO, full_source=video_source, source=video_source.lower())
    
    @staticmethod
    def from_podcast(title: str, host: str=None, date: str=None) -> 'Source':
        podcast_source = title
        if host:
            podcast_source += f" hosted by {host}"
        if date:
            podcast_source += f" ({date})"
        return Source(source_type=SourceType.PODCAST, full_source=podcast_source, source=podcast_source.lower())

    @staticmethod
    def from_other(source: str) -> 'Source':
        return Source(source_type=SourceType.OTHER, full_source=source, source=source.lower())