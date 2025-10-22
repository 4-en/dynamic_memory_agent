import sentence_transformers
import numpy as np
import torch.nn.functional as F
import logging

_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        logging.info("Loading sentence transformer model...")
        _embedder = sentence_transformers.SentenceTransformer('all-MiniLM-L6-v2')
    return _embedder

def embed_text(text:str | list[str]) -> np.ndarray:
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
    embeddings = embedder.encode(text, convert_to_tensor=True)
    # normalize the embeddings, which is often useful for similarity search
    tensor_embeddings = F.normalize(embeddings, p=2, dim=1 if type(text) is list else 0)
    return tensor_embeddings.cpu().numpy()

def embed_query(text:str | list[str]) -> np.ndarray:
    """
    Embed a query text using the MiniLM model.
    
    Parameters
    ----------
    text : str | list[str]
        The query text to embed.
        If a list of strings is provided, result will have shape (n, embedding_size).
    
    Returns
    -------
    np.array
        The embedding of the query text.
    """
    embedder = get_embedder()
    embeddings = embedder.encode_query(text, convert_to_tensor=True)
    # normalize the embeddings, which is often useful for similarity search
    tensor_embeddings = F.normalize(embeddings, p=2, dim=1 if type(text) is list else 0)
    return tensor_embeddings.cpu().numpy()

def embed_document(text:str | list[str]) -> np.ndarray:
    """
    Embed a document text using the MiniLM model.
    
    Parameters
    ----------
    text : str | list[str]
        The document text to embed.
        If a list of strings is provided, result will have shape (n, embedding_size).
    
    Returns
    -------
    np.array
        The embedding of the document text.
    """
    embedder = get_embedder()
    embeddings = embedder.encode_document(text, convert_to_tensor=True)
    # normalize the embeddings, which is often useful for similarity search
    tensor_embeddings = F.normalize(embeddings, p=2, dim=1 if type(text) is list else 0)
    return tensor_embeddings.cpu().numpy()


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Compute the cosine similarity between two vectors.
    Assumes the vectors are already normalized.
    
    Higher values indicate greater similarity.
    
    Parameters
    ----------
    vec1 : np.ndarray
        The first vector (normalized).
    vec2 : np.ndarray
        The second vector (normalized).

    Returns
    -------
    float
        The cosine similarity between the two vectors.
        [-1.0, 1.0]
    """
    return float(np.dot(vec1, vec2))


# preload the embedder
if _embedder is None:
    get_embedder()