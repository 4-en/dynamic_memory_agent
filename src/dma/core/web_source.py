from dataclasses import dataclass, field
from typing import List

# --- Dataclass for Article Data ---

@dataclass
class WebSourceData:
    """
    A dataclass to hold structured data for a single Wikipedia page.
    
    Attributes
    ----------
    title : str
        The title of the page.
    url : str
        The URL of the page.
    pageid : int
        The unique page ID.
    last_updated : str
        The last updated timestamp of the page.
    summary : str
        A brief summary of the page.
    content_plaintext : str
        The full plaintext content of the page.
    categories : list of str
        A list of category titles the page belongs to.
    links_to : list of str
        A list of titles of pages that this page links to.
    """
    title: str
    url: str
    pageid: int
    last_updated: str
    summary: str
    content_plaintext: str
    categories: List[str] = field(default_factory=list)
    links_to: List[str] = field(default_factory=list)