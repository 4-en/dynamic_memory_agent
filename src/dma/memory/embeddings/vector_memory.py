from abc import ABC, abstractmethod
import numpy as np

class VectorMemory(ABC):
    @abstractmethod
    def add_vector(self, vector: np.ndarray, metadata: dict):
        pass
    
    @abstractmethod
    def query(self, embedding: np.ndarray, top_k: int) -> list[dict]:
        pass
    
class FaissPlaceholder(VectorMemory):
    def add_vector(self, vector: np.ndarray, metadata: dict):
        # Placeholder implementation
        pass
    
    def query(self, embedding: np.ndarray, top_k: int) -> list[dict]:
        # Placeholder implementation
        return []