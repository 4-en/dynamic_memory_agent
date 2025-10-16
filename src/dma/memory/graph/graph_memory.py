
from abc import ABC, abstractmethod

class GraphMemory(ABC):
    @abstractmethod
    def add_entity(self, entity: str, attributes: dict):
        pass

    @abstractmethod
    def add_relationship(self, entity1: str, entity2: str, relationship: str):
        pass

    @abstractmethod
    def query(self, query: str) -> list:
        pass
    

class Neo4jPlaceholder(GraphMemory):
    def add_entity(self, entity: str, attributes: dict):
        # Placeholder implementation
        pass

    def add_relationship(self, entity1: str, entity2: str, relationship: str):
        # Placeholder implementation
        pass

    def query(self, query: str) -> list:
        # Placeholder implementation
        return []
    