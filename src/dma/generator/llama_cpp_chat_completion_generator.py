from .base_generator import BaseGenerator
from dma.core import Conversation, Message, Role, MessagePart, ThoughtPart, TextPart
from dma.config import DmaConfig, get_config
from llama_cpp import Llama, ChatCompletionRequestResponseFormat
from enum import Enum
import logging

class LlamaCppRole(Enum):
    """
    A collection of roles available for use with the Llama C++ framework.
    
    Parameters
    ----------
    Enum : str
        The role used by the OpenAI API.
    """
    
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class LlamaCppChatCompletionGenerator(BaseGenerator):
    """Generator for local models that use the Llama C++ framework."""
    
    def __init__(self):
        """
        Initialize the Llama C++ generator.

        Parameters
        ----------
        model_path : str
            The path to the model.
        hf_repo : str, optional
            The Hugging Face repository name, by default None
            If none, the model is assumed to be a local model.
        """
        
        self.config: DmaConfig = get_config()
        
        self.model_path = self.config.hf_file
        self.hf_repo = self.config.hf_repo if self.config.hf_repo != "local" else None
        
        
        self.model: Llama = None
        
        self._setup_generator()

    def _get_model_params(self) -> dict:
        """
        Get the model parameters.
        """

        n_ctx= self.config.llm_n_ctx if self.config.llm_n_ctx > 0 else 40960
        flash_attn = self.config.llm_flash_attn if self.config.llm_flash_attn is not None else True
        n_gpu_layers = self.config.llm_n_gpu_layers if self.config.llm_n_gpu_layers > 0 else 999
        verbose=False

        base_params = {
            "n_ctx": n_ctx,
            "flash_attn": flash_attn,
            "n_gpu_layers": n_gpu_layers,
            "verbose": verbose
        }

        return base_params

    def _setup_generator(self):
        """
        Setup the model for generating responses.
        """
        

        self.model = None

        logging.info("Setting up Llama C++ generator...")
        if self.hf_repo is None:
            self.model = Llama(self.model_path, **self._get_model_params())
        else:
            self.model = Llama.from_pretrained(self.hf_repo, self.model_path, **self._get_model_params())


    def convert_conversation_to_input(self, conversation: Conversation) -> list[dict]:
        """
        Convert a conversation to an input string for the generator.
        
        Parameters
        ----------
        conversation : Conversation
            The conversation to convert.
        
        Returns
        -------
        list[dict]
            The input for the generator.
        """
        messages = []
        for message in conversation.messages:
            role = LlamaCppRole.USER
            if message.role == Role.ASSISTANT:
                role = LlamaCppRole.ASSISTANT
            elif message.role == Role.SYSTEM:
                role = LlamaCppRole.SYSTEM
                
            messages.append({
                "role": role.value,
                "content": f"{message.message_text}"
            })
        return messages
    
    def convert_output_to_message(self, output:str) -> Message:
        """
        Convert the output from the OpenAI API to a Message.
        
        Parameters
        ----------
        output : str
            The output from the OpenAI API.
        
        Returns
        -------
        Message
            The message generated.
        """
        
        # if there is a </think> tag, seperate it
        cot = ""
        message = ""
        if "</think>" in output:
            cot = output.split("</think>", 1)
            if len(cot) == 2:
                output = cot[1]
                cot = cot[0].replace("<think>", "")
            else:
                output = cot[0]
                cot = ""


        parts = []
        if cot != "":
            parts.append(ThoughtPart(thought=cot))
        if output.strip() != "":
            parts.append(TextPart(text=output.strip()))
        message = Message(content=parts, role=Role.ASSISTANT)
        
        return message
        
    
    def generate(self, conversation: Conversation, json_format:bool=False) -> Message:
        """Generate a response based on the conversation.

        Parameters
        ----------
        conversation : Conversation
            The conversation to generate a response for.

        Returns
        -------
        Message
            The generated response.
        """
        if self.model is None:
            self._setup_generator()
        t = "text" if not json_format else "json"
        response_format = ChatCompletionRequestResponseFormat(type=t)        
        try:
            input = self.convert_conversation_to_input(conversation)
            output = self.model.create_chat_completion(
                messages=input,
                response_format=response_format,
                temperature=self.config.llm_temperature,
                top_p=self.config.llm_top_p,
                top_k=self.config.llm_top_k,
                max_tokens=self.config.llm_max_tokens_gen
            )
            
            return self.convert_output_to_message(output["choices"][0]["message"]["content"])
        except Exception as e:
            # TODO: handle exceptions
            raise e
        

        
    