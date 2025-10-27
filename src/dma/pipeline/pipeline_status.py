from dataclasses import dataclass
from enum import Enum

from dma.core.retrieval import RetrievalStep

class PipelineStatus(Enum):
    QUERY_GENERATION = "query_generation"
    QUERY_UPDATE = "query_update"
    RETRIEVAL = "retrieval"
    RETRIEVAL_UPDATE = "retrieval_update"
    RESPONSE_GENERATION = "response_generation"
    ERROR = "error"
    COMPLETED = "completed"
    
    
@dataclass
class PipelineUpdate:
    """
    Represents an update in the pipeline's status.
    
    Final status updates will have status=COMPLETED or status=ERROR."""
    status: PipelineStatus = PipelineStatus.QUERY_GENERATION
    message: str | None = None
    progress: float = 0.0
    retrieval_step: RetrievalStep | None = None