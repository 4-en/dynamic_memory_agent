
from abc import ABC, abstractmethod
from dma.core.memory import Memory, FeedbackType
from .graph_result import GraphResult

class GraphMemory(ABC):
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the graph database is connected.
        
        Returns
        -------
        bool
            True if connected, False otherwise.
        """
        pass
    
    @abstractmethod
    def reset_database(self, CONFIRM_DELETE: bool = False) -> bool:
        """Reset the graph database by deleting all nodes and relationships.
        
        Returns
        -------
        bool
            True if the database was reset successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    def add_memory(self, memory: Memory) -> bool:
        """Add a single memory to the graph database.
        Parameters
        ----------
        memory : Memory
            The memory object to add.
            
        Returns
        -------
        bool
            True if the memory was added successfully, False otherwise.
        """
        pass

    @abstractmethod
    def add_memory_batch(self, memories: list[Memory]) -> list[str]:
        """
        Add a batch of memories to the graph database.
        Parameters
        ----------
        memories : list[Memory]
            The list of memory objects to add.

        Returns
        -------
        list[str]
            A list of IDs for the added memories.
        """
        pass

    @abstractmethod
    def add_memory_series(self, memories: list[Memory]) -> bool:
        """
        Add a series of memories to the graph database.
        Memories in a series are linked together in order.
        Parameters
        ----------
        memories : list[Memory]
            The list of memory objects to add.
            
        Returns
        -------
        bool
            True if the series was added successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    def query_memories_by_id(self, memory_ids: list[str]) -> list[Memory]:
        """
        Query memories by their IDs.
        
        Parameters
        ----------
        memory_ids : list[str]
            The list of memory IDs to query.
        
        Returns
        -------
        list[Memory]
            The list of memories matching the IDs.
        """
        pass
    
    def query_memory_by_id(self, memory_id: str) -> Memory | None:
        """
        Query a single memory by its ID.
        
        Parameters
        ----------
        memory_id : str
            The ID of the memory to query.
        
        Returns
        -------
        Memory | None
            The memory matching the ID, or None if not found.
        """
        results = self.query_memories_by_id([memory_id])
        return results[0] if results else None
    
    @abstractmethod
    def query_memories_by_entities(self, entities: list[str], limit: int = 10) -> dict[list[GraphResult]]:
        """
        Query memories by entities.
        
        Parameters
        ----------
        entities : list[str]
            The list of entities to query.
        limit : int
            The maximum number of memories per entity to return.
        
        Returns
        -------
        dict[list[GraphResult]]
            A dictionary mapping each entity to a list of memories matching the query, along with their scores.
        """
        pass
    
    @abstractmethod
    def query_memories_by_vector(self, vector: list[float], top_k: int = 10) -> list[GraphResult]:
        """
        Query memories by vector similarity.
        
        Parameters
        ----------
        vector : list[float]
            The vector to query.
        top_k : int
            The number of top similar memories to return.
        
        Returns
        -------
        list[GraphResult]
            The list of memories matching the query, along with their scores.
        """
        pass
    
    @abstractmethod
    def connect_memories(self, memory_ids: list[str]) -> bool:
        """
        Connect a list of memories in the graph database.
        Basically strengthen relationships between them and create links if they don't exist.
        Allows for future traversal between related memories.
        
        Parameters
        ----------
        memories : list[str]
            The list of memory IDs to connect.

        Returns
        -------
        bool
            True if the memories were connected successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    def query_related_memories(self, memory_id: str, top_k: int = 10) -> list[GraphResult]:
        """
        Query memories related to a given memory.
        
        Parameters
        ----------
        memory_id : str
            The ID of the memory to find related memories for.
        top_k : int
            The number of top related memories to return.
        
        Returns
        -------
        list[GraphResult]
            The list of related memories along with their scores.
        """
        pass
    
    @abstractmethod
    def update_memory_access(self, memory_ids: list[str], feedback: FeedbackType = FeedbackType.NEUTRAL) -> list[str]:
        """
        Update the access information for a list of memories.
        Updates last accessed time and total access count.
        Also updates positive or negative feedback counts based on the feedback type.

        Parameters
        ----------
        memory_ids : list[str]
            The list of memory IDs to update.
        feedback : FeedbackType
            The type of feedback. One of {POSITIVE, NEGATIVE, NEUTRAL}.

        Returns
        -------
        list[str]
            The list of memory IDs that were successfully updated.
        """
        pass
    
    @abstractmethod
    def query_memory_series(self, origin_memory_id: str, previous: int = 2, next: int = 2) -> list[Memory]:
        """
        Query a series of memories linked to a given origin memory.
        Retrieves a specified number of previous and next memories in the series.

        Parameters
        ----------
        origin_memory_id : str
            The ID of the origin memory.
        previous : int
            The number of previous memories to retrieve.
        next : int
            The number of next memories to retrieve.

        Returns
        -------
        list[Memory]
            The list of memories in the series, including the origin memory.
        """
        pass

class Neo4jPlaceholder(GraphMemory):
    def is_connected(self) -> bool:
        return True
    
    def add_memory(self, memory: Memory) -> bool:
        return True

    def add_memory_batch(self, memories: list[Memory]) -> list[str]:
        return [str(i) for i in range(len(memories))]

    def add_memory_series(self, memories: list[Memory]) -> bool:
        return True

    def query_memories_by_id(self, memory_ids: list[str]) -> list[Memory]:
        return [Memory(id=mem_id) for mem_id in memory_ids]
    