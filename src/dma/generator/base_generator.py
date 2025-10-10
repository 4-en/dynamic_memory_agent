from dma.core import Conversation, Message, Role, MessagePart, ThoughtPart
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pydantic import BaseModel

@dataclass
class GeneratorConfig:
    """
    A configuration for a generator.
    This configuration is used to tune various parameters of the generator.
    
    Unifies different configurations for different generators.
    
    Attributes
    ----------
    temperature : float
        The temperature of the generator.
    max_tokens : int
        The maximum number of tokens to generate.
    top_p : float
        The nucleus sampling probability.
    top_k : int
        The nucleus sampling top-k value.
    frequency_penalty : float
        The frequency penalty.
    presence_penalty : float
        The presence penalty.
    stop : List[str]
        A list of stop words.
    """
    
    temperature: float = 0.7
    max_tokens: int = 1000
    top_p: float = 0.9
    top_k: int = 50
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: list[str] = field(default_factory=lambda: [])
    
    

class BaseGenerator(ABC):
    """
    Base class for a generator.
    A generator generates a response based on the conversation.
    """

    def __init__(self):
        """
        Initialize the generator.
        """
        pass

    @abstractmethod
    def generate(self, conversation:Conversation, context:str=None, response_format:BaseModel=None, **kwargs) -> Message:
        """
        Generate a response based on the conversation.

        Parameters
        ----------
        conversation : Conversation
            The conversation to generate a response for.
        context : str, optional
            The context of the conversation. Can include retrieved information,
            inner monologue, etc.
        response_format : BaseModel, optional
            The format of the model output.
            If None, the output will be a string.
            Otherwise, try to generate json output based on the model.
        kwargs : dict
            Additional keyword arguments for implementation-specific parameters.

        Returns
        -------
        Message
            The response generated.
        """
        pass
    
    def add_context_as_expert(self, conversation: Conversation, context: str) -> Conversation:
        """
        Add the context as a message from an expert to the conversation.
        
        This is useful for providing additional context to the model when the
        API only supports chat completion like OpenAI, and not direct access
        to token generation.
        
        Example:
        <User message> (prompt)
        <Expert message> (context)
        <Assistant message> (response)

        Parameters
        ----------
        conversation : Conversation
            The conversation to add the context to.
        context : str
            The context to add.

        Returns
        -------
        Conversation
            The conversation with the context added.
        """
        # TODO: test if context before prompt works better
        # (might make it easier for the model to attend to actual question)
        # last_message = conversation.messages[-1]

        summary = f"<Expert> {context}"
        message = Message(summary, Role.ASSISTANT)
        # insert the summary before the actual question
        # otherwise, some models might not be able to attend to the actual question
        # or interpret the summary as the message to respond to
        conversation.messages.append(message)
        return conversation
    
    def add_context_as_reasoning(self, conversation: Conversation, context: str) -> Conversation:
        """
        Add the context as reasoning to the conversation.
        
        This is useful for providing the model more natural access to the context,
        similarly to how it would generate a response based on its reasoning
        process.
        
        Example:
        <User message> (prompt)
        <Assistant message> (context) (response)

        Parameters
        ----------
        conversation : Conversation
            The conversation to add the context to.
        context : str
            The context to add.

        Returns
        -------
        Conversation
            The conversation with the context added.
        """
        reasoning = f"<think>{context}"
        
        reasoning_part = ThoughtPart(reasoning)
        
        message = Message(content=[reasoning_part], role=Role.ASSISTANT)
        conversation.messages.append(message)
        
        self._reasoning_message = message
        return conversation

    def clean_conversation_state(self, conversation: Conversation) -> Conversation:
        """
        Clean the conversation state to remove an injected context
        and avoid duplication.
        The generate method already returns the new Message, so the conversation
        shouldn't include the context message.
        
        Parameters
        ----------
        conversation : Conversation
            The conversation to clean.
        """
        
        # compare last message in conversation to generated message
        if len(conversation.messages) == 0:
            return conversation
        
        # compare last message in conversation to generated message
        if getattr(self, "_reasoning_message", None) is not None:
            if conversation.messages[-1] == self._reasoning_message:
                conversation.messages.pop(-1)
                self._reasoning_message = None