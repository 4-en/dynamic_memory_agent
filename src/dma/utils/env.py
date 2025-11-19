from dotenv import load_dotenv
from .app_paths import get_config_dir
import logging
import os

_ENV_LOADED = False
def load_env():
    global _ENV_LOADED
    if not _ENV_LOADED:
        config_dir = get_config_dir()
        dotenv_path = os.path.join(str(config_dir), ".env")
        load_dotenv(dotenv_path)
        _ENV_LOADED = True

def get_env_variable(var_name: str, add_to_dotenv: bool = True) -> str:
    """
    Get an environment variable, loading from .env if necessary.
    
    Parameters
    ----------
    var_name : str
        The name of the environment variable to retrieve.
    add_to_dotenv : bool, optional
        Whether to add the variable to the .env file if it is not set. Default is True.
        
    Returns
    -------
    str
        The value of the environment variable.
    """
    DOTENV_PLACEHOLDER = "CHANGE_ME"
    load_env()
    value = os.getenv(var_name, DOTENV_PLACEHOLDER)
    if value is not DOTENV_PLACEHOLDER:
        return value
    if not add_to_dotenv:
        return None
    config_dir = get_config_dir()
    dotenv_path = os.path.join(str(config_dir), ".env")
    with open(dotenv_path, "a") as f:
        f.write(f"\n{var_name}={DOTENV_PLACEHOLDER}\n")
    logging.warning(f"Environment variable '{var_name}' not set. Added to .env with placeholder value.")
    return None
        