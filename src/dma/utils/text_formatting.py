def split_text(text:str, max_length=1000) -> list[str]:
        """
        Split a long text into smaller chunks.
        If possible, try to split the text at logical points (e.g. at the end of a sentence).
        
        Parameters
        ----------
        text : str
            The text to split.
        
        Returns
        -------
        list[str]
            A list of smaller chunks of text.
        """
        seperators = ['\n\n', '\n', '. ', '! ', '? ']

        good_chunks = []

        while len(text) > max_length:
            chunk = text[:max_length]
            seperator = None
            for sep in seperators:
                if sep in chunk:
                    seperator = sep
                    break
            if seperator:
                last_pos = chunk.rfind(seperator)
                good_chunks.append(chunk[:last_pos])
                text = text[last_pos + len(seperator):]

            else:
                # no good seperator found, just split at max_length
                good_chunks.append(chunk)
                text = text[max_length:]
            
        good_chunks.append(text)
        return good_chunks

def chunk_text(text: str, chunk_size: int=1000, overlap: int=500, prefix: str='...', suffix: str='...') -> list[(str, str)]:
    """
    Split a long text into smaller chunks with a given size and overlap.
    
    Parameters
    ----------
    text : str
        The text to split.
    chunk_size : int, optional
        The size of each chunk, by default 1000
    overlap : int, optional
        The number of characters to overlap between chunks, by default 500
    prefix : str, optional
        A prefix to add to each chunk, by default '...'
    suffix : str, optional
        A suffix to add to each chunk, by default '...'
    
    Returns
    -------
    list[(str, str)]
        A list of smaller chunks of text and their chunk as a string in form of [start:end].
    """
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i + chunk_size]
        if i > 0:
            chunk = prefix + chunk
        if i + chunk_size < len(text):
            chunk += suffix
        chunks.append((chunk, f"[{i}:{i+chunk_size}]"))
    return chunks