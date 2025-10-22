# a step of the retrieval process, which includes query (entities, keywords, 
# embeddings), and the results (retrieved memories)
import numpy as np

from .memory import Memory, TimeRelevance
from .conversation import Conversation
from .message import Message
from dma.utils import embed_text

from dataclasses import dataclass, field

# notes:
# - add time relevance
# - add topic?

@dataclass
class EntityQuery:
    """Represents a query for a specific entity.
    
    Attributes
    ----------
    entity : str
        The entity to query.
    weight : float
        The weight of the entity in the query, higher means more important.
    """
    entity: str
    weight: float = 1.0
    
    @staticmethod
    def from_entity(entity: str, weight: float = 1.0):
        """
        Create an EntityQuery from a single entity string.
        
        Parameters
        ----------
        entity : str
            The entity to query.
        weight : float, optional
            The weight of the entity in the query, by default 1.0
            
        Returns
        -------
        EntityQuery
            The created EntityQuery instance.
        """
        if not entity:
            raise ValueError("entity must be provided")
        return EntityQuery(entity=entity, weight=weight)
    
    @staticmethod
    def from_entities(entities: list[str], weight: float = 1.0):
        """
        Create a list of EntityQuery from a list of entity strings.
        
        Parameters
        ----------
        entities : list[str]
            The list of entities to query.
        weight : float, optional
            The weight of each entity in the query, by default 1.0

        Returns
        -------
        list[EntityQuery]
            The created list of EntityQuery instances.
        """
        if not entities:
            return []
        return [EntityQuery.from_entity(entity, weight) for entity in entities]
    
@dataclass
class EmbeddingQuery:
    """Represents a query based on an embedding.
    
    Attributes
    ----------
    query_text : str
        The original text used to generate the embedding.
    embedding : np.ndarray | None
        The embedding vector for the query.
    weight : float
        The weight of the embedding in the query, higher means more important.
    """
    query_text: str
    embedding: np.ndarray | None = None
    weight: float = 1.0
    
    @staticmethod
    def from_text(query_text: str, weight: float = 1.0):
        """
        Create an EmbeddingQuery from a text string by embedding it.
        
        Parameters
        ----------
        query_text : str
            The text to embed for the query.
        weight : float, optional
            The weight of the embedding in the query, by default 1.0
        
        Returns
        -------
        EmbeddingQuery
            The created EmbeddingQuery instance.
        """
        if not query_text:
            raise ValueError("query_text must be provided")
        embedding = embed_text(query_text)
        return EmbeddingQuery(query_text=query_text, embedding=embedding, weight=weight)

@dataclass
class RetrievalQuery:
    """Represents a retrieval query, which can include entity queries and an embedding query.
    Entities and embedding should  be related to the same topic.
    At least one of entity_queries or embedding_query should be provided.
    
    Attributes
    ----------
    entity_queries : list[EntityQuery] | None
        A list of entity queries to use for retrieval.
    embedding_query : EmbeddingQuery | None
        An embedding query to use for retrieval.
    time_relevance : TimeRelevance
        The time relevance to use for the query.
    timestamp : float | None
        A specific timestamp to use for time relevance, if applicable.
    """
    entity_queries: list[EntityQuery] | None = None
    embedding_query: EmbeddingQuery | None = None
    time_relevance: TimeRelevance = TimeRelevance.UNKNOWN
    timestamp: float | None = None # A specific timestamp to use for time relevance, if applicable.
    
    @staticmethod
    def from_text(
        query_text: str, 
        entity_queries: list[EntityQuery] | None = None, 
        weight: float = 1.0,
        time_relevance: TimeRelevance = TimeRelevance.UNKNOWN,
        timestamp: float | None = None
    ):
        """Create a RetrievalQuery from text, with optional entity queries.
        If entity_queries is None or empty, only the embedding query will be used.
        
        Parameters
        ----------
        query_text : str
            The text to embed for the embedding query.
        entity_queries : list[EntityQuery] | None, optional
            A list of entity queries to include, by default None.
        weight : float, optional
            The weight of the embedding query, by default 1.0.
        time_relevance : TimeRelevance, optional
            The time relevance to use for the query, by default TimeRelevance.UNKNOWN.
        timestamp : float | None, optional
            A specific timestamp to use for time relevance, by default None.
            
        Returns
        -------
        RetrievalQuery
            The created RetrievalQuery instance.
        """
        embedding_query = EmbeddingQuery.from_text(query_text, weight)
        return RetrievalQuery(
            entity_queries=entity_queries,
            embedding_query=embedding_query,
            time_relevance=time_relevance,
            timestamp=timestamp
        )
        
    @staticmethod
    def from_entities(
        entities: list[str], 
        weight: float = 1.0,
        time_relevance: TimeRelevance = TimeRelevance.UNKNOWN,
        timestamp: float | None = None
    ):
        """Create a RetrievalQuery from a list of entities.
        Embedding query will be None.
        
        Parameters
        ----------
        entities : list[str]
            The list of entities to query.
        weight : float, optional
            The weight of each entity in the query, by default 1.0.
        time_relevance : TimeRelevance, optional
            The time relevance to use for the query, by default TimeRelevance.UNKNOWN.
        timestamp : float | None, optional
            A specific timestamp to use for time relevance, by default None.
            
        Returns
        -------
        RetrievalQuery
            The created RetrievalQuery instance.
        """
        
        return RetrievalQuery(
            entity_queries=EntityQuery.from_entities(entities, weight),
            time_relevance=time_relevance,
            timestamp=timestamp
        )

@dataclass
class MemoryResult:
    """Represents a retrieved memory and its associated score,
    calculated based on the relevance to the queries.
    
    Attributes
    ----------
    memory : Memory
        The retrieved memory.
    score : float
        The relevance score of the memory in relation to all queries.
    """
    memory: Memory
    score: float = 0.0

@dataclass
class RetrievalStep:
    """
    Represents a single step in the multi-step retrieval process, 
    including the queries made, the results obtained, and optional reasoning and summary.
    
    RetrievalStep results are used for the next step's queries.
    
    Attributes
    ----------
    queries : list[RetrievalQuery]
        The list of queries made in this retrieval step.
    results : list[MemoryResult]
        The list of results obtained from the queries.
    reasoning : str
        An optional reasoning about the queries.
    summary : str
        A summary of all retrieved memories.
    """
    queries: list[RetrievalQuery] = field(default_factory=list)
    results: list[MemoryResult] = field(default_factory=list)
    reasoning: str = "" # An optional reasoning about the queries
    summary: str = "" # A summary of all retrieved memories
    clarification_needed: bool = False # Whether clarification is needed for the next step
    is_pre_query: bool = False # Whether this step is a pre-query (to determine if clarification is needed)
    
@dataclass
class Retrieval:
    """Represents an iterative retrieval process, consisting of multiple retrieval steps.
    Retrieval stops when a satisfactory set of memories is found or a maximum number of steps is reached.
    The final_summary can be used to summarize the entire retrieval process and is used for the final output.
    
    Attributes
    ----------
    conversation : Conversation
        The conversation context for the retrieval.
    user_prompt : Message
        The original user prompt that initiated the retrieval.
    steps : list[RetrievalStep]
        The list of retrieval steps taken.
    final_summary : str
        A final summary of all retrieval steps.
    max_iterations : int
        Maximum number of retrieval iterations.
    current_iteration : int
        Current iteration count.
    done : bool
        Whether the retrieval process is complete.
    satisfactory : bool
        Whether the retrieved memories are satisfactory (as opposed to max_iterations reached).
    """
    conversation: Conversation = None # The conversation context for the retrieval
    user_prompt: Message = None # The original user prompt that initiated the retrieval
    steps: list[RetrievalStep] = field(default_factory=list)
    final_summary: str = "" # A final summary of all retrieval steps. This will be used as context for the final response.
    max_iterations: int = 3 # Maximum number of retrieval iterations
    current_iteration: int = 0 # Current iteration count
    done: bool = False # Whether the retrieval process is complete
    satisfactory: bool = False # Whether the retrieved memories are satisfactory (as opposed to max_iterations reached)
    _last_summary_count: int = -1 # internal counter to track if final summary has been updated
    
    def add_step(self, step: RetrievalStep):
        """Add a new retrieval step to the process.
        
        Parameters
        ----------
        step : RetrievalStep
            The retrieval step to add.
        """
        
        self.steps.append(step)
        self.current_iteration += 1
        if self.current_iteration >= self.max_iterations:
            self.done = True
            
    def mark_satisfactory(self):
        """Mark the retrieval as satisfactory and complete.
        This should be called when the QueryGenerator returns no new queries.
        """
        self.satisfactory = True
        self.done = True
        
    def needs_clarification(self) -> bool:
        """Check if any retrieval step indicated that clarification is needed.
        
        Returns
        -------
        bool
            True if clarification is needed, False otherwise.
        """
        # true if only one step and it indicates clarification needed
        # if the first step is a pre-query, we should check the second step
        if len(self.steps) == 0:
            return False
        if len(self.steps) == 1:
            return self.steps[0].clarification_needed
        
        if len(self.steps) == 2 and self.steps[0].is_pre_query:
            return self.steps[1].clarification_needed
        
        return False

    def finalize(self, force_new: bool=False) -> str:
        """Finalize the retrieval process by generating a final summary of all steps.
        
        Parameters
        ----------
        force_new : bool, optional
            Whether to force generating a new summary even if one already exists, by default False.
        
        Returns
        -------
        str
            The final summary of the retrieval process.
        """
        
        if self.needs_clarification():
            return "Okay, the user's prompt seems a bit unclear. I should ask for clarification before proceeding. First, "
        
        # count total memories in all steps
        total_memories = sum(len(step.results) for step in self.steps)
        
        if self.final_summary != "" and not force_new and self._last_summary_count == total_memories:
            return self.final_summary
        
        summaries = [step.summary for step in self.steps if step.summary]
        self.final_summary = "\n".join(summaries)
        
        if self.final_summary == "":
            self.final_summary = "Okay, this is what I know:\n"
            for step in self.steps:
                for result in step.results:
                    self.final_summary += f"- {result.memory.memory}\n"
            self.final_summary += "\nI should use think about the relevant information and then respond accordingly."
                    
        self._last_summary_count = total_memories
        
        return self.final_summary
    
