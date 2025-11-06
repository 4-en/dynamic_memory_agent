from pydantic import BaseModel
from .base_generator import BaseGenerator
from dma.core import Conversation, Message, Role, MessagePart, ThoughtPart, TextPart
from dma.config import DmaConfig, get_config
from llama_cpp import Llama
from .llama_cpp_chat_completion_generator import LlamaCppRole
import logging
from transformers import AutoTokenizer


# some llms for later
# bartowski/Llama-3.2-3B-Instruct-GGUF, *Q6_K.gguf
# unsloth/DeepSeek-R1-Distill-Qwen-7B-GGUF, *Q4_K_M.gguf
# unsloth/DeepSeek-R1-Distill-Qwen-14B-GGUF, *Q4_K_M.gguf
# unsloth/DeepSeek-R1-Distill-Qwen-1.5B-GGUF, *Q4_K_M.gguf
# unsloth/DeepSeek-R1-Distill-Qwen-3B-GGUF, *Q4_K_M.gguf
# bartowski/NousResearch_DeepHermes-3-Llama-3-8B-Preview-GGUF, *Q4_K_M.gguf


class LowLevelLlamaCppGenerator(BaseGenerator):
    """Generator for local models that use the Llama C++ framework with
    low-level API access for more control over the generation process."""
    
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
        self.tokenizer_repo = self.config.hf_tokenizer_override if self.config.hf_tokenizer_override else self.config.hf_repo
        
        self.model: Llama = None
        self.tokenizer: AutoTokenizer = None
        
        self._setup_generator()
        
    def _get_model_params(self) -> dict:
        """
        Get the model parameters.
        """

        n_ctx = self.config.llm_n_ctx if self.config.llm_n_ctx > 0 else 40960
        flash_attn = self.config.llm_flash_attn if self.config.llm_flash_attn is not None else True
        n_gpu_layers = self.config.llm_n_gpu_layers if self.config.llm_n_gpu_layers > 0 else 999
        verbose = False

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
        self.tokenizer = None

        logging.info("Setting up Llama C++ generator...")
        if self.hf_repo is None:
            self.model = Llama(self.model_path, **self._get_model_params())
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        else:
            self.model = Llama.from_pretrained(self.hf_repo, self.model_path, **self._get_model_params())
            self.tokenizer = AutoTokenizer.from_pretrained(self.tokenizer_repo)
        if self.tokenizer is None:
            # this is a hard error, we cannot properly proceed without a tokenizer
            # we could try ChatCompletion as a fallback, but that would defeat the purpose of this low-level generator
            if self.config.hf_tokenizer_override:
                raise ValueError("Tokenizer could not be loaded. Check the hf_tokenizer_override configuration.")
            else:
                raise ValueError("Tokenizer could not be loaded. Consider setting hf_tokenizer_override in the config file.")
            
    
    def generate_input_string(self, conversation: Conversation) -> str:
        """
        Generate the input string for the model based on the conversation.

        Parameters
        ----------
        conversation : Conversation
            The conversation to generate the input string for.

        Returns
        -------
        str
            The generated input string.
        """
        
        input_messages = []
        for message in conversation.messages:
            role = {
                Role.USER: LlamaCppRole.USER,
                Role.ASSISTANT: LlamaCppRole.ASSISTANT,
                Role.SYSTEM: LlamaCppRole.SYSTEM
            }.get(message.role, LlamaCppRole.USER).value
            
            content_str = ""
            
            # so far, we only support text and thought parts
            for part in message.get_parts():
                if isinstance(part, TextPart):
                    content_str += part.text
                elif isinstance(part, ThoughtPart):
                    print(f"Adding thought part: {part.thought}")
                    content_str += f"<think>{part.thought}</think>"
                    
            input_messages.append({
                "role": role,
                "content": content_str
            })
            
        # if the last message is from the assistant, we set
        # continue_final_message to True, and also remove the think closing tag
        # if it's the last part of the message
        continue_final_message = False
        if conversation.messages[-1].role == Role.ASSISTANT:
            continue_final_message = True
            if input_messages[-1]["content"].endswith("</think>"):
                input_messages[-1]["content"] = input_messages[-1]["content"][:-len("</think>")]
                
            print(f"Continuing final assistant message: {input_messages[-1]['content']}")
                
        input_str = self.tokenizer.apply_chat_template(
            input_messages,
            add_generation_prompt=not continue_final_message,
            tokenize=False,
            continue_final_message=continue_final_message
        )
        
        return input_str

    def generate_input_string_qwen2_basic(self, conversation: Conversation) -> str:
        """
        Generate the input string for the Qwen2 model based on the conversation.
        Very basic compared to the chat template version, but should work for simple cases.

        Parameters
        ----------
        conversation : Conversation
            The conversation to generate the input string for.

        Returns
        -------
        str
            The generated input string.
        """

        input_messages = []
        for message in conversation.messages:
            role = {
                Role.USER: LlamaCppRole.USER,
                Role.ASSISTANT: LlamaCppRole.ASSISTANT,
                Role.SYSTEM: LlamaCppRole.SYSTEM
            }.get(message.role, LlamaCppRole.USER).value

            content_str = ""

            # so far, we only support text and thought parts
            for part in message.get_parts():
                if isinstance(part, TextPart):
                    content_str += part.text
                elif isinstance(part, ThoughtPart):
                    content_str += f"<think>{part.thought}</think>"
                    
            # cleans up multiple think tags in a row
            # since models are mostly trained to have single think tags,
            # this should make it a bit more familiar to token generation
            # (might also do not help at all, but at least it's cleaner, and probably not worse)
            content_str = content_str.replace("</think><think>", "\n")

            input_messages.append({
                "role": role,
                "content": content_str
            })

        # if the last message is from the assistant, we set
        # continue_final_message to True, and also remove the think closing tag
        # if it's the last part of the message
        continue_final_message = False
        if conversation.messages[-1].role == Role.ASSISTANT:
            continue_final_message = True
            if input_messages[-1]["content"].endswith("</think>"):
                input_messages[-1]["content"] = input_messages[-1]["content"][:-len("</think>")]

        final_input_list = []
        # add messages
        for message in input_messages:
            name = "system"
            if message["role"] == LlamaCppRole.USER.value:
                name = "user"
            elif message["role"] == LlamaCppRole.ASSISTANT.value:
                name = "assistant"
            
            final_input_list.append(
                f"<|im_start|>{name}\n{message['content']}<|im_end|>"
            )
            
        if not continue_final_message:
            # add start for new message
            final_input_list.append(
                f"<|im_start|>assistant\n<think>"
            )
        else:
            # remove last <|im_end|> tag
            final_input_list[-1] = final_input_list[-1].replace("<|im_end|>", "")

        input_str = "\n".join(final_input_list)
        return input_str

    def convert_output_to_message(self, output:str, conversation: Conversation) -> Message:
        """
        Convert the output from llama_cpp to a Message.
        
        Parameters
        ----------
        output : str
            The output from the llama_cpp model.
        conversation : Conversation
            The conversation with previous messages.
        
        Returns
        -------
        Message
            The message generated.
        """
        
        # check if the conversation ended with an assistant message
        # in that case, we assume the output is a continuation
        
        # besides that, we have to properly separate the reasoning content
        # from the actual content, if it exists,
        # and combine it in the correct order
        
        output_message = Message(role=Role.ASSISTANT)
        
        if conversation.messages and conversation.messages[-1].role == Role.ASSISTANT:
            # if the last message was from the assistant, we assume this is a continuation
            output_message = conversation.messages[-1]
            # we remove the last message from the conversation, since the
            # output from the generator will be appended to the conversation
            # again, and we don't want to duplicate the last message
            conversation.messages.pop()
            
        # problem: we cannot assume at which point the generated content starts
        # it could be that the output is:
        # - a full message with reasoning and content
        # - a full message with only content
        # - a continuation of the last message with reasoning and content (no <think> tag)
        # - a continuation of the last message with only content (no <think> or </think> tag)
        # to be extremely safe, we should also check for multiple reasoning sections
        # (think <think>...</think>...<think>...</think>...)
        
        parts = []
        pos = 0
        while pos < len(output):
            think_start = output.find("<think>", pos)
            think_end = output.find("</think>", pos)
            
            if think_start == -1 and think_end == -1:
                # no more reasoning sections, we can take the rest as content
                parts.append(TextPart(output[pos:]))
                break
            
            if think_start != -1 and (think_end == -1 or think_start < think_end):
                # found a <think> tag, take the content before it as a text part
                if pos < think_start:
                    parts.append(TextPart(output[pos:think_start]))
                # take the reasoning content
                pos = think_start + len("<think>")
                reasoning_content = ""
                if think_end != -1:
                    reasoning_content = output[pos:think_end]
                    pos = think_end + len("</think>")
                parts.append(ThoughtPart(reasoning_content))
            else:
                # found a </think> tag, take the content before it as a reasoning part
                if pos < think_end:
                    parts.append(ThoughtPart(output[pos:think_end]))
                pos = think_end + len("</think>")
             
                
        if len(parts) == 0:
            # if no parts were found, we assume the output is empty
            return output_message
        
        if len(output_message.get_parts()) == 0:
            # if the output message has no parts, we can directly set the parts
            output_message.content = parts
        else:
            # otherwise, we append the parts to the existing content
            # if the last part type of the message matches the first part type,
            # we can append the content directly
            if isinstance(output_message.content[-1], TextPart) and isinstance(parts[0], TextPart):
                output_message.content[-1].text += parts[0].text
                parts.pop(0)
            elif isinstance(output_message.content[-1], ThoughtPart) and isinstance(parts[0], ThoughtPart):
                output_message.content[-1].thought += parts[0].thought
                parts.pop(0)
            output_message.content.extend(parts)
            
        
        return output_message
            
        
    def generate(self, conversation:Conversation, context:str=None, response_format:BaseModel=None, **kwargs) -> Message:
        """
        Generate a response based on the conversation.

        Parameters
        ----------
        conversation : Conversation
            The conversation to generate a response for.
            
        context : str, optional
            Additional context to provide to the model, by default None.
            
        response_format : BaseModel, optional
            The response format to use, by default None.
            Not supported in this generator.

        Returns
        -------
        Message
            The generated response message.
        """
        
        if response_format is not None:
            logging.warning("Response format is not supported in LowLevelLlamaCppGenerator. Ignoring.")
            
        if context is not None:
            conversation = self.add_context_as_reasoning(conversation, context)
        
        logging.info("Generating response...")

        message_str = self.generate_input_string_qwen2_basic(conversation)

        # print("=== Input to model ===")
        # print(message_str)
        # print("======================")
        
        # if we have a response format, we try to guide the llm to generate a json
        # response by prefilling the json structure after the <think> tags
        # for example: "<think>Here I am thinking about the answer.</think>\n{\n  \"answer\": \""
        response = None
        content = ""
        if response_format is None:
            response = self.model(
                prompt=message_str,
                max_tokens=self.config.llm_max_tokens_gen if self.config.llm_max_tokens_gen > 0 else None,
                temperature=self.config.llm_temperature,
                top_p=self.config.llm_top_p,
                top_k=self.config.llm_top_k,
            )
            content = response["choices"][0]["text"]
        else:
            schema = response_format.model_json_schema()
            properties = schema.get('properties', {})
            first_field = list(properties.keys())[0] if properties else None
            start_json = "{\n  "
            if first_field:
                start_json += f'"{first_field}": "'
                
            last_think_open = message_str.rfind("<think>")
            last_think_close = message_str.rfind("</think>")
            think_first = last_think_open > last_think_close
            
            # we let the model think first, then generate the json structure
            if think_first:
                think_response = self.model(
                    prompt=message_str,
                    max_tokens=self.config.llm_max_tokens_gen if self.config.llm_max_tokens_gen > 0 else None,
                    temperature=self.config.llm_temperature,
                    top_p=self.config.llm_top_p,
                    top_k=self.config.llm_top_k,
                    stop=["</think>"]
                )
                think_content = think_response["choices"][0]["text"]
                # now generate the json part
                json_prompt = message_str + think_content + "</think>\n" + start_json
                response = self.model(
                    prompt=json_prompt,
                    max_tokens=self.config.llm_max_tokens_gen if self.config.llm_max_tokens_gen > 0 else None,
                    temperature=self.config.llm_temperature,
                    top_p=self.config.llm_top_p,
                    top_k=self.config.llm_top_k
                )
                content = think_content + "</think>\n" + start_json + response["choices"][0]["text"]
            else:
                # generate the json part directly
                json_prompt = message_str + start_json
                response = self.model(
                    prompt=json_prompt,
                    max_tokens=self.config.llm_max_tokens_gen if self.config.llm_max_tokens_gen > 0 else None,
                    temperature=self.config.llm_temperature,
                    top_p=self.config.llm_top_p,
                    top_k=self.config.llm_top_k
                )
                content = start_json + response["choices"][0]["text"]
            
        
        logging.info("Response generated.")
        
        
        
        return self.convert_output_to_message(content, conversation)
        



def custom_llama3_converter(chat: list[dict]) -> str:
    """
    custom chat converter for llama-3 based models

    <|begin_of_text|><|start_header_id|>system<|end_header_id|>
    {system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>
    {prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
    """
    parts = []
    # parts.append("<|begin_of_text|>")
    is_last_assistant = False
    for i, message in enumerate(chat):
        role = message["role"]
        is_last_assistant = role == "assistant" and i == len(chat) - 1

        content = message["content"]
        parts.append(f"<|start_header_id|>{role}<|end_header_id|>")
        parts.append(content)

        # inject assistant response and leave open ended if last message is from assistant
        if not is_last_assistant:
            parts.append("<|eot_id|>")
    
    if not is_last_assistant:
        parts.append("<|start_header_id|>assistant<|end_header_id|>")

    return "".join(parts)
        

def custom_chatml_converter(chat: list[dict]) -> str:
    """
    custom chat converter for chatml based models

    <|im_start|>{role}
    {prompt}<|im_end|>
    <|im_start|>{role}
    {prompt}<|im_end|>
    ...
    """
    parts = []
    # parts.append("<|begin_of_text|>")
    is_last_assistant = False
    for i, message in enumerate(chat):
        role = message["role"]
        is_last_assistant = role == "assistant" and i == len(chat) - 1
        parts.append(f"<|im_start|>{role}")
        parts.append(message["content"])
        if not is_last_assistant:
            parts.append("<|im_end|>")

    if not is_last_assistant:
        parts.append("<|im_start|>assistant\n")

    return "\n".join(parts)

def format_output(output: str) -> str:
    # replace /n in the output with actual newlines
    output = output.replace("\\n", "\n")
    return output


