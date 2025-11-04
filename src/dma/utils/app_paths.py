# defines common paths used in the application
# for storing configurations, logs, cache, and data files.

# XDG for Linux/macOS and AppData for Windows

import os
from pathlib import Path

APP_NAME = "dynamic_memory_agent"

def get_config_dir() -> Path:
    """Get the configuration directory path."""
    if os.name == 'nt':  # Windows
        base_dir = Path(os.getenv('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    else:  # Linux and macOS
        base_dir = Path(os.getenv('XDG_CONFIG_HOME', Path.home() / '.config'))
    config_dir = base_dir / APP_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

def get_log_dir() -> Path:
    """Get the log directory path."""
    if os.name == 'nt':  # Windows
        base_dir = Path(os.getenv('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    else:  # Linux and macOS
        base_dir = Path(os.getenv('XDG_CACHE_HOME', Path.home() / '.cache'))
    log_dir = base_dir / APP_NAME / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir

def get_cache_dir() -> Path:
    """Get the cache directory path."""
    if os.name == 'nt':  # Windows
        base_dir = Path(os.getenv('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    else:  # Linux and macOS
        base_dir = Path(os.getenv('XDG_CACHE_HOME', Path.home() / '.cache'))
    cache_dir = base_dir / APP_NAME / 'cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir

def get_data_dir() -> Path:
    """Get the data directory path."""
    if os.name == 'nt':  # Windows
        base_dir = Path(os.getenv('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    else:  # Linux and macOS
        base_dir = Path(os.getenv('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
    data_dir = base_dir / APP_NAME / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

def get_default_paths() -> dict:
    """Get a dictionary of default application paths."""
    return {
        'config': get_config_dir(),
        'logs': get_log_dir(),
        'cache': get_cache_dir(),
        'data': get_data_dir(),
    }
