from dataclasses import dataclass, field
from .message import Message
from uuid import uuid4


@dataclass
class Conversation:
    """
    Conversation class to represent a conversation.

    Attributes
    ----------
    messages : list
        The list of messages in the conversation.
    id : str
        The conversation id.
    """
    
    # The list of messages in the conversation.
    messages: list[Message] = field(default_factory=list)

    # The conversation id.
    id: str = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid4())
            
    def copy(self):
        """
        Create a copy of the conversation.
        
        Returns
        -------
        Conversation
            The copy of the conversation.
        """
        return Conversation(messages=self.messages.copy(), id=self.id)

    def add_message(self, message: Message):
        """
        Add a message to the conversation.
        
        Parameters
        ----------
        message : Message
            The message to be added.
        """
        self.messages.append(message)

    def get_last_messages(self, n: int):
        """
        Get the last n messages in the conversation.
        
        Parameters
        ----------
        n : int
            The number of messages to retrieve.
            If n is greater than the total number of messages,
            all messages will be returned.
            If n is less than or equal to 0, or the conversation is empty,
            an empty list will be returned.

        Returns
        -------
        list : list[Message]
            The list of the last n messages in the conversation.
        """
        if n <= 0 or not self.messages:
            return []
        
        if n >= len(self.messages):
            return self.messages
        
        return self.messages[-n:]
    
    def estimate_tokens(self):
        """
        Estimate the number of tokens in the conversation.
        
        Returns
        -------
        int
            The estimated number of tokens in the conversation.
        """
        return sum([message.estimate_tokens() for message in self.messages])
