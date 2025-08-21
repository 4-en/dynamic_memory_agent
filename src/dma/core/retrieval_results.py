from dataclasses import dataclass, field
import sentence_transformers
import numpy as np
from uuid import uuid4
from dma.utils import split_text, chunk_text
from enum import Enum
from dma.core import TimeRelevance, Memory
from time import time

class RetrieverType(Enum):

    MEMORY = 'MEMORY'
    LOCAL = 'LOCAL'
    WEB = 'WEB'
    OTHER = 'OTHER'

class QueryType(Enum):
    GENERAL = 'GENERAL'
    PERSONAL = 'PERSONAL'
    NEWS = 'NEWS'
    RESEARCH = 'RESEARCH'
    OTHER = 'OTHER'

    def __str__(self):
        return self.value
    
    def __repr__(self):
        return self.value
    
    @staticmethod
    def from_string(value: str) -> 'QueryType':
        lower_value = value.lower()
        if lower_value == 'general':
            return QueryType.GENERAL
        elif lower_value == 'personal':
            return QueryType.PERSONAL
        elif lower_value == 'news':
            return QueryType.NEWS
        elif lower_value == 'research':
            return QueryType.RESEARCH
        elif lower_value == 'other':
            return QueryType.OTHER
        else:
            # Default to other
            return QueryType.OTHER

@dataclass
class Query:
    """
    A class to hold a query.
    
    Attributes
    ----------
    query : str
        The query string.
    topic : str
        The topic of the query.
    query_type : QueryType
        The type of the query.
    query_id : str
        The id of the query.
    time_relevance : TimeRelevance
        The relevance of the query in time.
    embedding : np.ndarray
        The embedding of the query.
    entities : list[str]
        The entities in the query.
    """
    
    query: str
    topic: str
    query_type: QueryType
    query_id: str | None = None
    time_relevance: TimeRelevance = TimeRelevance.UNKNOWN
    target_time: float = field(default_factory=lambda: time())
    embedding: np.ndarray | None = None
    entities: list[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.query_id is None:
            self.query_id = str(uuid4())
            
    def __eq__(self, value):
        if not isinstance(value, Query):
            return False
        
        if self.query_id or value.query_id:
            return self.query_id == value.query_id
        
        return self.query == value.query and self.topic == value.topic and self.query_type == value.query_type
 
@dataclass
class QueryResult:
    # TODO: include actual memory object
    """
    A class to hold a query result.
    
    Attributes
    ----------
    result : str
        The result string.
    query : Query
        The query that generated the result.
    embedding : np.ndarray | None = None
        The embedding of the result.
    score : float | None = None
        The score of the result compared to the query.
    source : str | None = None
        The source of the result. For example, a URL.
    source_title : str | None = None
        The title of the source.
    retriever : RetrieverType | None = None
        The type of retriever that retrieved the result.
    parent : QueryResult | None = None
        The parent query result.
        In case a long result is split into multiple parts.
    parent_part_index : int | None = None
        The index of the parent part.
        Can be used to order the parts and combine them if needed.
    memory : Memory | None = None
        The memory object associated with the result.
        Can be None if the result is not a memory, eg. a web result.
    """
    
    result: str
    query: Query
    embedding: np.ndarray | None = None
    score: float | None = None
    source: str | None = None
    source_title: str | None = None
    retriever_type: RetrieverType | None = RetrieverType.OTHER
    parent: 'QueryResult' = None
    parent_part_index: int | None = None
    memory: Memory = None
    
    def __eq__(self, value):
        if not isinstance(value, QueryResult):
            return False
        
        return self.result == value.result and self.query == value.query

    def __hash__(self):
        return hash((self.result, self.query))

    def __str__(self):
        return self.result
    
    def __repr__(self):
        return f"QueryResult({self.result}, {self.query})"
    
    def __len__(self):
        return len(self.result)
    
    def __getitem__(self, index):
        return self.result[index]
    
    def __iter__(self):
        return iter(self.result)
    
    def add_parent(self, parent: 'QueryResult', part_index: int):
        """
        Add a parent to the query result.
        
        Parameters
        ----------
        parent : QueryResult
            The parent query result.
        part_index : int
            The index of the parent part."""
        self.parent = parent
        self.parent_part_index = part_index
    
    def add_embedding(self, embedding: np.ndarray):
        self.embedding = embedding
    
    def add_score(self, score: float):
        self.score = score
        
    def split_result(self, max_length: int) -> list['QueryResult']:
        if len(self.result) <= max_length:
            return [self]
        
        text_parts = split_text(self.result, max_length)
        query_parts = [QueryResult(text_part, self.query) for text_part in text_parts]
        for i, query_part in enumerate(query_parts):
            query_part.add_parent(self, i)
            query_part.source = self.source
            query_part.retriever = self.retriever
            
        return query_parts
    
    def chunk_result(self, chunk_size: int=700, overlap: int=400) -> list['QueryResult']:
        if len(self.result) <= chunk_size:
            return [self]
        
        text_parts = chunk_text(self.result, chunk_size, overlap)
        query_parts = [QueryResult(text_part, self.query, source=source) for text_part, source in text_parts]
        for i, query_part in enumerate(query_parts):
            query_part.add_parent(self, i)
            query_part.retriever_type = self.retriever_type
            query_part.source_title = self.source_title
            
        return query_parts
    

class RetrievalResults:
    """
    A class to hold the results of a retrieval operation.
    This can include the results of multiple queries.

    Attributes
    ----------
    results : Dict[str, list[QueryResults]]
        The results of the retrieval operation, grouped by query.
    summaries: List[str]
        The summaries of the results.
        This can include context from the evaluator or summaries
        based on the retrieved results.
    """
    
    ranker = None
    
    def __init__(self):
        if RetrievalResults.ranker is None:
            from aiko.retriever import BaseRanker
            RetrievalResults.ranker = BaseRanker
            
        self.results: dict[str, list[QueryResult]] = {}
        self._sources = {} # stores results by soure to avoid duplicates
        self.summaries: list[str] = []
        


    
    def add_result(self, query_result: QueryResult):
        """
        Add a result to the retrieval results.
        
        Parameters
        ----------
        query_result : QueryResult
            The result to add.
        """
        
        if query_result.source in self._sources:
            # Avoid duplicates
            return
            
        
        # TODO: add more control over how results are split.
        # This should be controlled either by the pipeline or by the config file
        if len(query_result.result) > 1600:
            # Split long results into smaller parts
            query_parts = query_result.chunk_result(1500, 500)
            for query_part in query_parts:
                self.add_result(query_part)
            return
        
        if query_result.query.query_id not in self.results:
            self.results[query_result.query.query_id] = [ query_result ]
        else:
            self.results[query_result.query.query_id].append(query_result)
            

            
        

    def __len__(self) -> int:
        """
        Return the number of results.
        
        Returns
        -------
        int
            The number of results.
        """
        n = 0
        for query_id in self.results:
            n += len(self.results[query_id])
        return n
    
    def rank_results(self) -> None:
        """
        Rank the results based on the scoring method and adjust their scores.

        """
        
        # TODO: use config
        RetrievalResults.ranker.rank(self, "cosine")
        
    def is_ranked(self) -> bool:
        """
        Check if the results are ranked.
        
        Returns
        -------
        bool
            True if the results are ranked, False otherwise.
        """
        
        for query_id in self.results:
            for result in self.results[query_id]:
                if result.score is None:
                    return False
        return True
    

    def purge(self, min_score: float=0.0, max_results: int=None, min_query_results: int=1):
        """
        Purge the results based on the minimum score and the maximum number of results.
        
        Parameters
        ----------
        min_score : float, optional
            The minimum score of the results. The default is 0.0.
        max_results : int, optional
            The maximum number of results to keep. The default is None.
        min_query_results : int, optional
            The minimum number of results to keep for each query. The default is 1.
            This bypasses the max_results parameter (if n_queries * min_query_results > max_results), but not the min_score parameter.
        """
        top_results = self.top_k(max_results, min_score, min_query_results=min_query_results)
        self.results = {}
        self._sources = {}
        for result in top_results:
            self.add_result(result)
        
    
    def top_k(self, k: int | None, min_score: float | None=None, query: Query | None=None, min_query_results: int=1) -> list[QueryResult]:
        """
        Get the top k results.
        
        Parameters
        ----------
        k : int
            The number of top results to get.
            If k is None, return all results.
        min_score : float, optional
            The minimum score of the results. The default is None.
        query : Query, optional
            The query to get the top results for. If None, get the top results for all queries in one ranking.
            The default is None.
        min_query_results : int, optional
            The minimum number of results to keep for each query.
            The default is 1.
            This bypasses the k parameter (if n_queries * min_query_results > k), but not the min_score parameter.
            
        Returns
        -------
        List[QueryResult]
            The top k results.
        """
        
        if not self.is_ranked():
            self.rank_results()
        
        results = []
        
        if query is not None:
            # Get results for a specific query
            if query.query_id in self.results:
                query_results = self.results[query.query_id]
                query_results.sort(key=lambda x: x.score, reverse=True)
                if k is not None:
                    results = query_results[:k]
                else:
                    results = query_results
            else:
                return []
        else:
            # Get results for all queries
            all_results = []
            for query_id in self.results:
                all_results.extend(self.results[query_id])
            all_results.sort(key=lambda x: x.score, reverse=True)
            if k is not None:
                included_queries = dict()
                results = []
                remaining = []
                if(min_query_results > 0):
                    # first make sure we have at least min_query_results for each query
                    for result in all_results:
                        if result.query.query_id not in included_queries:
                            results.append(result)
                            included_queries[result.query.query_id] = 1
                        elif included_queries[result.query.query_id] < min_query_results:
                            results.append(result)
                            included_queries[result.query.query_id] += 1
                        else:
                            remaining.append(result)
                        
                    # then add the remaining results if needed
                    if len(results) < k:
                        results.extend(remaining[:k-len(results)])
                        # sort again
                        results.sort(key=lambda x: x.score, reverse=True)
                else:
                    results = all_results[:k]
                
            else:
                results = all_results
                
        if min_score is not None:
            results = [result for result in results if result.score >= min_score]
            
        return results
        
    def extend(self, other):
        """
        Extend the results with the results from another RetrievalResults object.
        
        Parameters
        ----------
        other : RetrievalResults
            The other RetrievalResults object to extend the results with.
        """
        for query_id in other.results:
            if query_id not in self.results:
                self.results[query_id] = other.results[query_id]
            else:
                self.results[query_id].extend(other.results[query_id])





    

