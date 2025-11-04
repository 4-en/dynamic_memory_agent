import os
from pathlib import Path
from dma.utils import get_config_dir

APP_NAME = "dynamic_memory_agent"

def get_config_path() -> Path:
    """Find the configuration file path in a prioritized order."""

    # 1. Check for an environment variable
    if env_path_str := os.getenv("DMA_CONFIG_PATH"):
        env_path = Path(env_path_str)
        # if its not a file, append config.yaml
        if not env_path.is_file():
            env_path = env_path / "config.yaml"
        
        if not env_path.exists():
            # mkdir the parent directory if it doesn't exist
            env_path.parent.mkdir(parents=True, exist_ok=True)
        return env_path


    user_config_dir = get_config_dir()
    user_config_path = user_config_dir / "config.yaml"
    if not user_config_path.exists():
        user_config_path.parent.mkdir(parents=True, exist_ok=True)
    return user_config_path

def get_first_existing_path(paths) -> Path:
    """Return the first existing path from a list of paths."""
    for path in paths:
        if path.exists():
            return path
    return None