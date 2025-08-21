import sentence_transformers
import numpy as np
import logging

_embedder = None

def get_embedder():
    if _embedder is None:
        logging.info("Loading sentence transformer model...")
        _embedder = sentence_transformers.SentenceTransformer('all-MiniLM-L6-v2')
    return _embedder

def embed_text(text:str | list[str]) -> np.array:
    """
    Embed a text using the MiniLM model.
    
    Parameters
    ----------
    text : str | list[str]
        The text to embed.
        If a list of strings is provided, result will have shape (n, embedding_size).
    
    Returns
    -------
    np.array
        The embedding of the text.
    """
    embedder = get_embedder()
    return embedder.encode(text)