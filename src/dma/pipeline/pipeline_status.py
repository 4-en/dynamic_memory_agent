from dataclasses import dataclass
from enum import Enum

from dma.core.retrieval import RetrievalStep

class PipelineStatus(Enum):
    QUERY_GENERATION = "query_generation"
    RETRIEVAL = "retrieval"
    RESPONSE_GENERATION = "response_generation"
    COMPLETED = "completed"
    
class PipelineUpdateType(Enum):
    NONE = "none"
    QUERY = "query"
    RETRIEVAL = "retrieval"
    RESPONSE = "response"
    ERROR = "error"
    
@dataclass
class PipelineUpdate:
    status: PipelineStatus = PipelineStatus.QUERY_GENERATION
    update_type: PipelineUpdateType = PipelineUpdateType.NONE
    message: str | None = None
    progress: float = 0.0
    retrieval_step: RetrievalStep | None = None