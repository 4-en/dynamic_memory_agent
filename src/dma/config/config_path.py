import os
from pathlib import Path

APP_NAME = "dynamic_memory_agent"

def get_config_path() -> Path:
    """Find the configuration file path in a prioritized order."""

    # 1. Check for an environment variable
    if env_path_str := os.getenv("DMA_CONFIG_PATH"):
        env_path = Path(env_path_str)
        if not env_path.exists():
            # mkdir the parent directory if it doesn't exist
            env_path.parent.mkdir(parents=True, exist_ok=True)
        return env_path

    # 2. Check the user's OS-specific config directory
    # On Windows, this is %APPDATA%; on Linux/macOS, it's ~/.config
    user_config_dir = Path(os.getenv("APPDATA") or Path.home() / ".config")
    user_config_path = user_config_dir / APP_NAME / "config.yaml"
    if not user_config_path.exists():
        user_config_path.parent.mkdir(parents=True, exist_ok=True)
    return user_config_path

def get_first_existing_path(paths) -> Path:
    """Return the first existing path from a list of paths."""
    for path in paths:
        if path.exists():
            return path
    return None