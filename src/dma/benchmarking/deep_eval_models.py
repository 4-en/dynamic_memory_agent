# wrapper around models so deepeval can use them

from deepeval.models.base_model import DeepEvalBaseLLM, DeepEvalBaseEmbeddingModel
from dma.pipeline import Pipeline
from dma.core import Conversation, Message, Role, Memory
from dma.utils import embed_text

class DynMemLLM(DeepEvalBaseLLM):
    def __init__(self, model_name:str, pipeline:Pipeline):
        self.model_name = "DynMem_" + model_name
        self.pipeline = pipeline

    def load_model(self):
        return self.model_name

    def generate(self, prompt: str) -> str:
        # basic string to string generation using the pipeline
        conversation = Conversation()
        conversation.add_message(Message(role=Role.USER, content=prompt))
        response = self.pipeline.generate(conversation)
        return response.message_text
    
    def generate_with_context(self, prompt: str) -> tuple[str, list[str]]:
        # generate with additional context if needed
        conversation = Conversation()
        conversation.add_message(Message(role=Role.USER, content=prompt))
        response = self.pipeline.generate(conversation)
        return response.message_text, [memory.memory for memory in response.source_memories]
        
    
    async def a_generate(self, prompt: str) -> str:
        # no async support since this is for local pipelines
        return self.generate(prompt)
    
    def generate_message(self, conversation: Conversation) -> Message:
        return self.pipeline.generate(conversation)

    def get_model_name(self):
        return self.model_name
    
class BaselineLLM(DeepEvalBaseLLM):
    def __init__(self, model_name:str, pipeline:Pipeline):
        self.model_name = "Baseline_" + model_name
        self.pipeline = pipeline

    def load_model(self):
        return self.model_name
    
    def _add_instructions(self, conversation:Conversation) -> Conversation:
        if len(conversation.messages)>0 and conversation.messages[0].role == Role.SYSTEM:
            print("Warning: System prompt already present, not adding instructions.")
            return conversation
        # add any necessary instructions to the conversation before generation
        # for baseline models, we might want to add a system prompt
        system_prompt = "You are a helpful assistant. Answer the user's questions to the best of your ability."
        conversation.messages.insert(0, Message(role=Role.SYSTEM, content=system_prompt))
        return conversation


    def generate(self, prompt: str) -> str:
        # basic string to string generation using the pipeline
        conversation = Conversation()
        conversation.add_message(Message(role=Role.USER, content=prompt))
        conversation = self._add_instructions(conversation)
        response = self.pipeline.generator.generate(conversation)
        return response.message_text
    
    def generate_with_context(self, prompt: str) -> tuple[str, list[str]]:
        # generate with additional context if needed
        conversation = Conversation()
        conversation.add_message(Message(role=Role.USER, content=prompt))
        conversation = self._add_instructions(conversation)
        response = self.pipeline.generator.generate(conversation)
        return response.message_text, []
    
    async def a_generate(self, prompt: str) -> str:
        # no async support since this is for local pipelines
        return self.generate(prompt)
    
    def generate_message(self, conversation: Conversation) -> Message:
        conversation = conversation.copy()
        conversation = self._add_instructions(conversation)
        return self.pipeline.generator.generate(conversation)

    def get_model_name(self):
        return self.model_name
    
class BaselineRAGLLM(DeepEvalBaseLLM):
    def __init__(self, model_name:str, pipeline:Pipeline):
        self.model_name = "BaselineRAG_" + model_name
        self.pipeline = pipeline

    def load_model(self):
        return self.model_name
    
    def _add_context(self, conversation:Conversation) -> tuple[Conversation, list[Memory]]:
        # add any necessary context to the conversation before generation
        # for RAG baseline models, we might want to add retrieved context
        
        instruction = Message(
            role=Role.SYSTEM,
            content="You are a helpful AI assistant. Reply to the user and use the expert's information when available, without mentioning the expert."
        )
        
        if len(conversation.messages)==0 or conversation.messages[0].role != Role.SYSTEM:
            conversation.messages.insert(0, instruction)
            
        prompt = conversation.messages[-1].message_text
        embedding = embed_text(prompt or "").tolist()
        
        memories = self.pipeline.retriever.graph_memory.query_memories_by_vector(
            vector=embedding,
            top_k=10
        )
        
        if len(memories) > 0:
            retrieval_text = "<EXPERT>\nHere is some information from an expert that may help you:\n\n"
            for res in memories:
                retrieval_text += f"- {res.memory.memory}\n"
            retrieval_message = Message(
                role=Role.USER,
                content=retrieval_text
            )
            conversation.messages.append(retrieval_message)
        return conversation, [ res.memory for res in memories ]

    def generate(self, prompt: str) -> str:
        # basic string to string generation using the pipeline
        conversation = Conversation()
        conversation.add_message(Message(role=Role.USER, content=prompt))
        conversation, _ = self._add_context(conversation)
        response = self.pipeline.generator.generate(conversation)
        return response.message_text
    
    def generate_with_context(self, prompt: str) -> tuple[str, list[str]]:
        # generate with additional context if needed
        conversation = Conversation()
        conversation.add_message(Message(role=Role.USER, content=prompt))
        conversation, memories = self._add_context(conversation)
        response = self.pipeline.generator.generate(conversation)
        return response.message_text, [memory.memory for memory in memories]
    
    async def a_generate(self, prompt: str) -> str:
        # no async support since this is for local pipelines
        return self.generate(prompt)
    
    def generate_message(self, conversation: Conversation) -> Message:
        conversation = conversation.copy()
        conversation, memories = self._add_context(conversation)
        output = self.pipeline.generator.generate(conversation)
        output.source_memories = memories
        return output

    def get_model_name(self):
        return self.model_name
    
class LocalEmbeddingModel(DeepEvalBaseEmbeddingModel):
    def __init__(self):
        self.model_name = "all-MiniLM-L6-v2"

    def load_model(self):
        return self.model_name

    def get_embedding(self, text: str) -> list[float]:
        return embed_text(text).tolist()
    
    def embed_text(self, text: str) -> list[float]:
        return embed_text(text).tolist()
    
    def a_embed_text(self, text: str) -> list[float]:
        return embed_text(text).tolist()
    
    def get_model_name(self):
        return self.model_name
    
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return embed_text(texts).tolist()
    
    def a_embed_texts(self, texts: list[str]) -> list[list[float]]:
        return embed_text(texts).tolist()