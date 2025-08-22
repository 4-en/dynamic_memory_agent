from .config import Config

import dataclasses

@dataclasses.dataclass
class DmaConfig(Config):
    """
    General configuration for Dynamic Memory Agent (DMA).
    """
    
    
    # LLM configuration
    # add comment to the config file by using cc_ prefix (str or callable or str(x))
    cc_hf_model: str = "The Hugging Face model to use"
    cc_hf_local_note: str = "Set hf_repo to 'local' to use a local model"
    #hf_repo: str = "Qwen/QwQ-32B-GGUF"
    #hf_file: str = "qwq-32b-q4_k_m.gguf"
    hf_repo: str = "unsloth/Qwen3-14B-GGUF"
    hf_file: str = "*Q4_K_M.gguf"
    
    
    # Generator configuration
    cc_llm_instruction: str = "The instruction to use for the LLM"
    llm_instruction: str = "You are a helpful assistant."
    
    cc_llm_gen_settings: int = "The settings for the underlying LLM."
    llm_max_tokens_gen: int = -1
    llm_n_gpu_layers: int = -1
    llm_n_ctx: int = -1
    llm_flash_attn: bool = True
    llm_verbose: bool = False
    
    cc_llm_sampling_settings: str = "The sampling settings for the LLM."
    llm_temperature: float = 0.7
    llm_top_p: float = 0.95
    llm_top_k: int = 40
    
    cc_context_injection_method: str = "The method to use for context injection. Options are 'reasoning' or 'expert'."
    context_injection_method: str = "reasoning"

_config_instance: DmaConfig = None
def get_config() -> DmaConfig:
    global _config_instance
    if _config_instance is None:
        _config_instance = DmaConfig()
    return _config_instance