from dma.core.memory import Memory

from dataclasses import dataclass

@dataclass
class GraphResult:
    memory: Memory
    score: float