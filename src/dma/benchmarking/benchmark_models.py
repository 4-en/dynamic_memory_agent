# several dataclasses that define benchmark models for DMA system
from dataclasses import dataclass, field
from enum import Enum

class LearningTestMode(Enum):
    """
    Enum for different learning test modes.
    
    - ALL: Run iterations with all data available.
    - SPLIT: "Train" on part of the data, then "test" on the rest.
    """
    ALL = "all"
    SPLIT = "split"

@dataclass
class BenchmarkKnowledgeBase:
    name: str
    description: str
    type: str = "wikipedia"
    categories: list[str] = field(default_factory=list)
    learning_test_mode: LearningTestMode = LearningTestMode.ALL
    iterations: int = 1 # number of times to run the benchmark, used to benchmark learning over time
    
@dataclass
class BenchmarkResult:
    model_name: str
    benchmark_name: str
    accuracy: float
    latency: float
    details: dict = field(default_factory=dict)