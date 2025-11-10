# evaluates retrieved memory contents and scores/filters them based on relevance

from pydantic import BaseModel, Field

from dma.core import Memory, Retrieval, RetrievalStep, RetrievalQuery, EntityQuery, EmbeddingQuery, Message, Conversation, Role
from dma.generator import BaseGenerator, LowLevelLlamaCppGenerator
from enum import Enum
import logging

from dataclasses import dataclass, field

class MemoryRelevance(Enum):
    UNKNOWN = "unknown"
    NONSENSE = "nonsense"
    IRRELEVANT = "irrelevant"
    RELEVANT = "relevant"
    PERFECT = "perfect"
    
    
class MemoryEvaluation(BaseModel):
    memory_id_int: int
    short_feedback_str: str = ""
    memory_keywords_list: list[str] = Field(default_factory=list)
    relevance_str: str
    
class EvaluationResult(BaseModel):
    evaluations_list: list[MemoryEvaluation] = Field(default_factory=list)
    summary_str: str = ""
    missing_keywords_list: list[str] = Field(default_factory=list)
    
_example_json = """
Example response (assuming the context is about "Zero-knowledge proof" in cryptography):
{
    "evaluations_list": [
        {
            "memory_id_int": 1,
            "short_feedback_str": "Highly relevant to the query since it contains an example for Zero-knowledge proof.",
            "memory_keywords_list": ["Zero-knowledge proof", "cryptography"],
            "relevance_str": "PERFECT"
        },
        {
            "memory_id_int": 2,
            "short_feedback_str": "Barely relevant, only tangentially related to cryptographic concepts, but not what was asked.",
            "memory_keywords_list": ["cryptography", "RSA", "encryption"],
            "relevance_str": "IRRELEVANT"
        },
        {
            "memory_id_int": 3,
            "short_feedback_str": "Not relevant at all, does not pertain to the topic of Zero-knowledge proofs and doesn't make sense in general.",
            "memory_keywords_list": ["cats", "pets", "secret cat society", "conspiracy"],
            "relevance_str": "NONSENSE"
        }
    ],
    "summary_str": "In cryptography, a Zero-knowledge proof is a method by which one party can prove to another party that one statement is true, without conveying any information beyond the validity of the statement itself..."
}
"""

_format_json = """
The response should be a JSON object matching the following format:
<think>
Reasoning and summary about what kind of information we need and then the relevance of each memory to the query.
</think>
{
    "evaluations_list": [ # list of evaluation objects, one per memory
        {
            "memory_id_int": <int>, # ID of the memory being evaluated from the list of provided memories
            "short_feedback_str": "<string>", # brief explanation of the relevance score
            "memory_keywords_list": ["<string>", ...], # list of keywords the memory is about
            "relevance_str": <string: "NONSENSE" | "IRRELEVANT" | "RELEVANT" | "PERFECT"> # relevance rating of the memory to the query. NONSENSE for information that doesn't make sense, IRRELEVANT for information that is unrelated, RELEVANT for information that is somewhat related and useful, PERFECT for information that directly answers the query
        },
        ...
    ],
    "summary_str": "<string>", # summary of all the relevant information from the memories with relevance score 2 or 3, structured as a coherent explanation
    "missing_keywords_list": ["<string>", ...] # (optional) list of important keywords or entities that were not found in any of the memories but are relevant to the query
}
"""

_instructions = """
You are to evaluate the retrieved memories based on their relevance to a given query and conversation context.
Rate them based on how well they address the query and would be useful when replying to the user.
Consider the following when evaluating:
- Direct relevance to the query
- Usefulness of the information in the memory for constructing a response
- Coherence and clarity of the memory content

After the reasoning step (inside <think></think> tags), immediately provide the JSON response without any additional text.
"""

@dataclass
class Evaluation:
    summary: str = ""
    memories: list[Memory] = field(default_factory=list)
    ratings: list[MemoryRelevance] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    
    def get_relevant_memories(self, threshold: MemoryRelevance=MemoryRelevance.RELEVANT) -> list[Memory]:
        """
        Get memories with relevance scores above the given threshold.
        
        Parameters
        ----------
        threshold : MemoryRelevance
            The minimum relevance for a memory to be considered relevant.
            
        Returns
        -------
        list[Memory]
            List of relevant memories.
        """
        # since we cannot be sure with UNKNOWN, give it priority when its a memory property, and act as lowest when its a threshold
        ordered_relevance = [MemoryRelevance.NONSENSE, MemoryRelevance.IRRELEVANT, MemoryRelevance.RELEVANT, MemoryRelevance.PERFECT, MemoryRelevance.UNKNOWN]
        threshold_index = ordered_relevance.index(threshold) if threshold != MemoryRelevance.UNKNOWN else 0
        relevant_memories = [mem for mem, rating in zip(self.memories, self.ratings) if ordered_relevance.index(rating) >= threshold_index]
        return relevant_memories
    
    def get_with_relevance(self) -> list[tuple[Memory, MemoryRelevance]]:
        """
        Get list of tuples containing memories and their relevance scores.
        
        Returns
        -------
        list[tuple[Memory, MemoryRelevance]]
            List of tuples of memories and their relevance ratings.
        """
        return list(zip(self.memories, self.ratings))




class MemoryEvaluator:
    def __init__(self, generator: BaseGenerator):
        self.generator = generator

    def evaluate_memories(
        self,
        retrieval_step: RetrievalStep,
        conversation: Conversation
    ) -> Evaluation:
        """
        Evaluate the relevance of memories to the retrieval step's query.
        
        Parameters
        ----------
        memories : list[Memory]
            List of memories to evaluate.
        retrieval_step : RetrievalStep
            The retrieval step containing the query.
        conversation : Conversation
            The conversation context.
            
        Returns
        -------
        Evaluation
            The evaluation result containing relevance scores and summary.
        """
        memories = retrieval_step.results
        if len(memories) == 0 or retrieval_step.queries == None or len(retrieval_step.queries) == 0:
            logging.warning("No memories or queries to evaluate; returning empty evaluation.")
            return None
        
        prompt_conversation = self._build_prompt(memories, retrieval_step, conversation)
        
        reply_beginning = (
            "Okay, first I should examine what the conversation and the provided queries are about, then "
            "I will evaluate each memory one by one based on their relevance to the queries and conversation context. "
            "Finally, I will provide a summary of the relevant information found in the memories.\n"
        )
        
        result = self.generator.generate_object(
            conversation=prompt_conversation,
            response_format=EvaluationResult,
            context=reply_beginning)
        
        success = result.success
        if not success:
            logging.error("Memory evaluation generation failed.")
            return None
        evaluation = self._parse_evaluation_result(result.result, memories)
        return evaluation
        
    def _parse_evaluation_result(self, result: EvaluationResult, memories: list[Memory]) -> Evaluation:
        """
        Parse the evaluation result into an Evaluation object.
        
        Parameters
        ----------
        result : EvaluationResult
            The raw evaluation result from the generator.
        memories : list[Memory]
            The list of memories that were evaluated.
            
        Returns
        -------
        Evaluation
            The parsed evaluation object.
        """
        evaluations = result.evaluations
        memory_list = []
        scores = []
        
        for e in evaluations:
            mem_id = e.memory_id_int - 1  # assuming memory IDs are 1-based
            if mem_id < 0 or mem_id >= len(memories):
                logging.warning(f"Invalid memory ID {mem_id+1} in evaluation result; skipping.")
                continue  # skip invalid memory IDs
            relevance = e.relevance_str.lower()
            mem_relevance = None
            match relevance:
                case "nonsense":
                    mem_relevance = MemoryRelevance.NONSENSE
                case "irrelevant":
                    mem_relevance = MemoryRelevance.IRRELEVANT
                case "relevant":
                    mem_relevance = MemoryRelevance.RELEVANT
                case "perfect":
                    mem_relevance = MemoryRelevance.PERFECT
            if mem_relevance == None:
                logging.warning(f"Unknown relevance '{e.relevance_str}' for memory ID {mem_id+1}; setting to UNKNOWN.")
                mem_relevance = MemoryRelevance.UNKNOWN
            memory_list.append(memories[mem_id])
            scores.append(mem_relevance)
            
        if len(memory_list) != len(memories):
            logging.warning("Some memories were missing in the evaluation result; assigning UNKNOWN relevance to them.")
            # add missing memories with UNKNOWN relevance
            for mem in memories:
                if mem not in memory_list:
                    memory_list.append(mem)
                    scores.append(MemoryRelevance.UNKNOWN)
            
        evaluation = Evaluation(
            summary=result.summary_str,
            memories=memory_list,
            ratings=scores,
            missing_keywords=result.missing_keywords_list
        )
        return evaluation
        
        

    def _build_prompt(
        self,
        memories: list[Memory],
        retrieval_step: RetrievalStep,
        conversation: Conversation
    ) -> Conversation:
        """
        Build the prompt conversation for memory evaluation.
        
        Parameters
        ----------
        memories : list[Memory]
            List of memories to evaluate.
        retrieval_step : RetrievalStep
            The retrieval step containing the query.
        conversation : Conversation
            The conversation context.
            
        Returns
        -------
        Conversation
            The constructed prompt conversation.
        """
        # Build the prompt for evaluation
        prompt = "Evaluate the following memories based on their relevance to the provided conversation and queries."
        
        # add the memories, conversation, and query to the prompt
        memories_str = ""
        for i, mem in enumerate(memories):
            memories_str += f"Memory ID {i+1}:\n{mem.memory}\n\n"
        prompt += f"\n\n## Memories:\n{memories_str}"
        
        LAST_N_CONVERSATION_MESSAGES = 10
        recent_conversation = conversation.messages[-LAST_N_CONVERSATION_MESSAGES:]
        conversation_str = ""
        for msg in recent_conversation:
            conversation_str += f"{msg.role.value}: {msg.content}\n"
        prompt += f"\n\n## Conversation Context:\n{conversation_str}"
        
        query_str = ""
        for query in retrieval_step.queries:
            if query.embedding_query:
                query_str += f"- {query.embedding_query.query_text}\n"

        prompt += f"\n\n## Queries:\n{query_str}"
        
        prompt += "\n\nPlease provide your evaluation in the specified JSON format."
        # Create the full prompt conversation
        prompt_messages = [
            Message(
                role=Role.SYSTEM,
                content=f"{_instructions}\n{_format_json}\n{_example_json}"
            ),
            Message(
                role=Role.USER,
                content=prompt
            )
        ]
        
        return Conversation(messages=prompt_messages)
