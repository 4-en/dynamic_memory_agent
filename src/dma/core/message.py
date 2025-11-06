from dataclasses import dataclass, field
from time import time
from uuid import uuid4
# from aiko.utils.estimate_tokens import estimate_tokens
from enum import Enum
from abc import ABC, abstractmethod

class Role(Enum):
    """
    A collection of roles available for use.

    Parameters
    ----------
    Enum : str
        The role used by the system.
    """
    
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


def estimate_tokens(text: str) -> int:
    """
    Dummy function to estimate tokens in a string.
    In a real implementation, this would use a tokenizer to count tokens.
    Uses average of 4 characters per token as a rough estimate.
    
    Parameters
    ----------
    text : str
        The text to estimate tokens for.
    
    Returns
    -------
    int
        The estimated number of tokens.
    """
    return len(text) // 4 + 1

class ContentType(Enum):
    """
    Represents the content type of a message.
    """
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    THOUGHT = "thought"


class MessagePart:
    """
    Base class for message parts.
    """

    @abstractmethod
    def to_dict(self) -> dict:
        """
        Convert the message part to a dictionary.

        Returns
        -------
        dict
            The dictionary representation of the message part.
        """
        pass

    


@dataclass
class TextPart(MessagePart):
    """
    Text part of a message.

    Attributes
    ----------
    text : str
        The text content of the message part.
    """
    text: str = ""

    def to_dict(self) -> dict:
        """
        Convert the message part to a dictionary.

        Returns
        -------
        dict
            The dictionary representation of the message part.
        """
        return {
            "type": ContentType.TEXT.value,
            "text": self.text
        }

    def __str__(self) -> str:
        """
        Return the string representation of the text part.

        Returns
        -------
        str
            The string representation of the text part.
        """
        return self.text
    
    def __repr__(self) -> str:
        """
        Return the string representation of the text part.

        Returns
        -------
        str
            The string representation of the text part.
        """
        return self.text
    
@dataclass
class ThoughtPart(MessagePart):
    """
    Thought part of a message / reasoning.

    Attributes
    ----------
    thought : str
        The thought content of the message part.
    """
    thought: str = ""

    def to_dict(self) -> dict:
        """
        Convert the message part to a dictionary.

        Returns
        -------
        dict
            The dictionary representation of the message part.
        """
        return {
            "type": ContentType.THOUGHT.value,
            "text": f"<think>{self.thought}</think>"
        }

    def __str__(self) -> str:
        """
        Return the string representation of the thought part.

        Returns
        -------
        str
            The string representation of the thought part.
        """
        return self.thought
    
    def __repr__(self) -> str:
        """
        Return the string representation of the thought part.

        Returns
        -------
        str
            The string representation of the thought part.
        """
        return self.thought

@dataclass
class Message:
    """
    Represents a message in the conversation.

    Attributes
    ----------
    content : str | list[MessagePart]
        The message content.
    timestamp : str
        The timestamp of the message.
    id : str
        The message id.
    role : Role
        The role of the user who sent the message.
    entities : list[str]
        Entities mentioned in the message.
    source_ids : list[str]
        Source ids used in retrieval (for assistant messages).
    embedding : list[float] | None
        Embedding vector for message text content.
    """

    # The message content.
    content: str | list[MessagePart] = field(default_factory=list)
    
    # The role of the user who sent the message.
    role: Role = Role.USER


    # The timestamp of the message.
    timestamp: str = None

    # The message id.
    id: str = None
    
    # entities mentioned in the message, with count of mentions
    entities: dict[str, int] = field(default_factory=dict)
    
    # source ids used in retrieval (for assistant messages)
    source_ids: list[str] = field(default_factory=list)
    
    # embedding vector for message text content
    embedding: list[float] = None


    def __post_init__(self):
        """
        Initialize the message.
        """
        if self.timestamp is None or self.timestamp == "":
            self.timestamp = str(time())


        if self.id is None:
            self.id = str(uuid4())
            
        if self.content is None:
            self.content = []
        elif isinstance(self.content, str):
            self.content = [TextPart(self.content)]
            
    def add_content(self, content: MessagePart | str):
        """
        Add content to the message.

        Parameters
        ----------
        content : MessagePart
            The content to add to the message.
        """
        if self.content is None:
            self.content = []
        
        if type(self.content) is str:
            self.content = [TextPart(self.content)]
            
        if type(content) is str:
            content = TextPart(content)
        
        self.content.append(content)
            
    def get_formatted(self) -> str:
        """
        Return the formatted message.

        Returns
        -------
        str
            The formatted message.
        """
        # TODO: implement this function as a general way to format messages.
        # It should work for openai style chat completions.
        # It should contain the following:
        # [time] <user>: <message>
        # [time] <assistant>: <response>
        #
        # Time should be formatted as a human-readable (so llm readable) time, like "DD/MM/YYYY HH:MM:SS"
        # User and assistant should be formatted as their names.
        
        return f"<{self.user.name}> {self.message_text}"

    @property
    def message_text(self) -> str:
        """
        Return the text content of the message.

        Returns
        -------
        str
            The text content of the message.
        """
        if self.content is None:
            return ""
        
        if type(self.content) is str:
            return self.content
        
        if type(self.content) is list:
            return "\n".join([part.text for part in self.content if type(part) is TextPart])
        
        return self.content
        
    @message_text.setter
    def message_text(self, value: str):
        """
        Set the text content of the message.

        Parameters
        ----------
        value : str
            The text content of the message.
        """
        self.content = [TextPart(value)]
        
    @property
    def full_text(self) -> str:
        """
        Return the full text content of the message, including thoughts.

        Returns
        -------
        str
            The full text content of the message.
        """
        if self.content is None:
            return ""
        
        if type(self.content) is str:
            return self.content
        
        if type(self.content) is list:
            return "\n".join([part.text if type(part) is TextPart else f"<think>{part.thought}</think>" for part in self.content])
        
        return self.content

    @property
    def reasoning_text(self) -> str:
        """
        Return the reasoning text content of the message.

        Returns
        -------
        str
            The reasoning text content of the message.
        """
        if self.content is None:
            return ""
        
        if type(self.content) is list:
            return "\n".join([part.thought for part in self.content if type(part) is ThoughtPart])
        
        if type(self.content) is str:
            return ""
        
        return ""


    def add_text(self, text: str):
        """
        Add text content to the message.

        Parameters
        ----------
        text : str
            The text content to add to the message.
        """
        if type(self.content) is str:
            self.content = [TextPart(self.content)]

        if self.content is None:
            self.content = []
        
        self.content.append(TextPart(text))

    def add_thought(self, thought: str):
        """
        Add thought content to the message.

        Parameters
        ----------
        thought : str
            The thought content to add to the message.
        """
        if type(self.content) is str:
            self.content = [TextPart(self.content)]

        if self.content is None:
            self.content = []
        
        self.content.append(ThoughtPart(thought))
    
    def get_parts(self) -> list[MessagePart]:
        """
        Return the message parts.

        Returns
        -------
        list[MessagePart]
            The message parts.
        """
        if self.content is None:
            self.content = []
        elif isinstance(self.content, str):
            self.content = [TextPart(self.content)]
        return self.content


    def __str__(self) -> str:
        """
        Return the string representation of the message.

        Returns
        -------
        str
            The string representation of the message.
        """
        return f"{self.message_text}"
    
    def __repr__(self) -> str:
        """
        Return the string representation of the message.

        Returns
        -------
        str
            The string representation of the message.
        """
        return f"{self.message_text}"
    
    def estimate_tokens(self) -> int:
        """
        Estimate the number of tokens in the message content.

        Returns
        -------
        int
            The estimated number of tokens in the message content.
        """
        return estimate_tokens(f"<{self.user.name}> {self.message_text}")

