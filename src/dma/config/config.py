from dataclasses import dataclass, field
from json import loads, dumps
import os
import logging
from .config_path import get_config_path, get_first_existing_path
from pathlib import Path

class Config:
    """
    A class that can be used to create a configuration object.
    Objects can be loaded from or saved to a file.
    Date in files is stored in the following schema:
    
    ```python
        # A comment
        key=value
        key2=[value1, value2] #json array
        key3={key4=value4, key5=value5} #json object
    ```
        
    All attributes starting with an underscore (_) are considered private and will not be saved or loaded.
    
    Attributes starting with an "cc_" are treated as comments and will be written to the file 
    as comments, but will not be loaded.
    If an attribute starting with "cc_" followed by the name of another attribute is found, 
    it will be treated as a comment for that attribute
    and will be written in the line before the attribute.
    
    Comments should either be a string or a callable that returns a string.
    
    Other attributes are considered public and will be saved and loaded.
    """
    
    def __init__(self, file_name=None, attributes=None):
        """
        Initialize the configuration object.
        This can either be used by inheriting from this class or by creating an instance of this class and passing the attributes as a dictionary.

        Parameters
        ----------
        file_name : str, optional
            The name of the file to load the configuration from.
            If None, the default file name will be used.
        attributes : dict, optional
            A dictionary of attributes to initialize the configuration
        """
        super().__init__()
        
        if file_name:
            if (not "/" in file_name) and (not "\\" in file_name):
                # if no path is given, we try to find a config path
                config_path = get_config_path()
                file_name = str(config_path.parent / file_name)
        
        self.__file_name = file_name
        if attributes:
            for key, value in attributes.items():
                if not hasattr(self, key):
                    setattr(self, key, value)
        
    def load(self, file_name=None, create_if_missing=True, prioritize_environment=False):
        """
        Load the configuration from the file.
        
        Parameters
        ----------
        file_name : str
            The name of the file to load the configuration from.
            If None, the default file name will be used.
        create_if_missing : bool, optional
            Whether to create a new file if the file does not exist. The default is True.
        prioritize_environment : bool, optional
            If True, environment variables matching the configuration keys will override the values in the file.
            
        Returns
        -------
        ConfigClass (or subclass)
            The configuration object itself.
        """
        fields = {}
        
        if file_name:
            if (not "/" in file_name) and (not "\\" in file_name):
                # if no path is given, we try to find a config path
                config_path = get_config_path()
                file_name = str(config_path.parent / file_name)
        
        if hasattr(self, "__file_name"):
            file_name = file_name or self.__file_name or "config.cfg"
        else:
            file_name = file_name or "config.cfg"
            self.__file_name = file_name
            
        if file_name == "config.cfg":
            logging.warning("Using default config file name 'config.cfg'. It's recommended to specify a config file name or path.")
            
        read_file_name = get_first_existing_path([Path(file_name), Path(self.__file_name), Path("./" + Path(file_name).name)])
            
        didnt_exist = False
        if not os.path.exists(file_name):
            didnt_exist = True
            if create_if_missing:
                logging.info(f"File {file_name} does not exist. Creating a new one.")
                self.save(file_name)
            else:
                logging.warning(f"File {file_name} does not exist.")

        if not read_file_name:
            return self
            
        annotations = getattr(self, "__annotations__", {})
        has_annotations = bool(annotations)
        
        
        with open(read_file_name, "r") as file:
            for line in file:
                try:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    key, value = line.split("=", 1)
                    value = value.strip()
                    
                    # check for environment variable override
                    if prioritize_environment and key in os.environ:
                        value = os.environ[key]
                    
                    if value.startswith("["):
                        value = loads(value)
                    elif value.startswith("{"):
                        value = loads(value)
                    else:
                        value_type = str
                        try:
                            # try to get a type annotation from the default value
                            if has_annotations and key in annotations:
                                value_type = annotations[key]
                            else:
                                value_type = type(getattr(self, key))
                                
                            if value_type == type(None):
                                # if we can't get the type from the default value, we try to guess it from the loaded value
                                # this is not 100% reliable, but it's better than nothing
                                if value == "None":
                                    value = None
                                elif value.lower() == "true" or value.lower() == "false":
                                    value_type = bool
                                elif value.isdigit():
                                    value_type = int
                                elif value.replace(".", "", 1).isdigit():
                                    value_type = float
                                else:
                                    value_type = str
                        except:
                            logging.error(f"Error getting type for {key}")

                        if value == None:
                            fields[key] = None
                        else:
                            if value_type == bool:
                                value = bool(value)
                            elif value_type == int:
                                value = int(value)
                            elif value_type == float:
                                value = float(value)
                            elif value_type == str:
                                value = str(value)
                                # replace any escaped newlines
                                value = value.replace("\\n", "\n")
                    fields[key] = value
                except Exception as e:
                    logging.error(f"Error loading line: {line}")
                    logging.error(e)
                    
        missed_fields = 0
        
        for key, value in self.__dict__.items():
            if key.startswith("_") or key.startswith("cc_"):
                continue
            
            if key not in fields:
                missed_fields += 1
            else:
                setattr(self, key, fields[key])
                    
        if missed_fields > 0:
            logging.warning(f"Loaded configuration from {file_name} with {missed_fields} missing fields.")
            if create_if_missing:
                logging.warning("Regenerating default values for missing fields...")
                self.save(file_name)
        elif didnt_exist and create_if_missing:
            logging.info(f"Created new configuration file {file_name}.")
            self.save(file_name)
                
        return self
        
        
    def save(self, file_name=None):
        """
        Save the configuration to the file.
        
        Parameters
        ----------
        file_name : str, optional
            The name of the file to save the configuration to.
            If None, the file name that was used to load will be used.
        """
        file_name = file_name or self.__file_name
        
        # make sure path exists
        path = os.path.dirname(file_name)
        if path and not os.path.exists(path):
            os.makedirs(path)
        
        with open(file_name, "w") as file:
            for key, value in self.__dict__.items():
                try:
                    # skip private attributes
                    if key.startswith("_"):
                        continue
                    
                    # write comments at position if they don't belong to an attribute
                    if key.startswith("cc_"):
                        no_under = key[3:]
                        if not hasattr(self, no_under):
                            comment = value
                            if callable(comment):
                                comment = comment()
                            comment = str(comment)
                            for line in comment.split("\n"):
                                file.write(f"# {line}\n")
                        continue
                    
                    # write comments for attributes
                    comment = getattr(self, f"cc_{key}", None)
                    if comment:
                        if callable(comment):
                            comment = comment()
                        comment = str(comment)
                        for line in comment.split("\n"):
                            file.write(f"# {line}\n")
                    
                    # write the attribute
                    if isinstance(value, list) or isinstance(value, dict):
                        value = dumps(value)
                    elif isinstance(value, str):
                        # escape newlines
                        value = value.replace("\n", "\\n")
                    file.write(f"{key}={value}\n")
                    
                except Exception as e:
                    logging.error(f"Error saving {key}")
                    logging.error(e)


@dataclass
class ConfigTest(Config):
    """
    Config class to represent the configuration of the assistant.

    Attributes
    ----------
    name : str
        The name of the assistant.
    description : str
        The description of the assistant.
    version : str
        The version of the assistant.
    """
    
    cc_name: str = "The name of the assistant"
    name: str = "Aiko"
    
    cc_id: str = "The id of the assistant"
    id: str = "aiko"
    
    cc_description: str = "The description of the assistant"
    description: str = "An AI assistant."
    
    cc_version: str = "The version of the assistant"
    version: str = "1.0"
    
    cc_instructions: str = "The instructions for the assistant"
    instructions: str = "You are a helpful assistent named Aiko. You are generally helpful, unless someone gives you a reason not to be, in which case you can be a bit sassy."

    cc_max_input_length: str = "The maximum number of input characters"
    max_input_length: int = 4096

    cc_cut_off_window: str = "The length of window used to cut off tokens when len(tokens) > max_input_length"
    cut_off_window: int = 2048

    cc_log_conversations: str = "Whether to log the conversations"
    loggings: bool = False

    cc_log_dir: str = "Where to log the conversations"
    log_dir: str = "logs"
    
    cc_max_generated_tokens: str = "The maximum number of tokens to generate"
    max_generated_tokens: int = 512
    cc_temperature: str = "The temperature for sampling, higher values make the model more creative"
    temperature: float = 1.3
    cc_top_k: str = "The number of tokens to sample from, lower values make the model more conservative"
    top_k: int = 50
    cc_top_p: str = "The cumulative probability for nucleus sampling, higher values make the model more creative"
    top_p: float = 0.9
    
    cc_max_generated_queries: str = "The maximum number of queries to generate for information retrieval"
    max_generated_queries: int = 3
    cc_max_retrieved_info: str = "The max amount of passsages to use when generating summaries"
    max_retrieved_info: int = 6
    cc_max_eval_input_messages: str = "The last n messages of the conversation to use a context for query generation"
    max_evaluation_input_messages: int = 10
    cc_enable_pre_evaluation_retrieval: str = "Whether to enable pre-evaluation retrieval\nThis will retrieve information before the evaluation of the response based on the raw user input"
    enable_pre_evaluation_retrieval: bool = True
    cc_max_retrieval_depth: str = "The maximum depth of the retrieval tree"
    max_retrieval_depth: int = 1
    