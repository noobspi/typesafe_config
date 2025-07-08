import os
from pathlib import Path
import logging
import tomllib
import json
from typing import TypeVar, Type, get_args, Any
from pydantic import BaseModel, ValidationError

import sys  # Für den Zugriff auf Kommandozeilenargumente
import re  # Für das Parsen von Argumenten

# Initialize logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Define a TypeVar for the Pydantic model itself
TConfigModel = TypeVar("TConfigModel", bound="ConfigModel")


class ConfigAttrMetadata(BaseModel):
    model: str
    name: str
    fullanme: str
    type: str
    raw_type: Any
    description: str = ""
    default: Any = None


class ConfigModel(BaseModel):
    """
    Super-Easy and Type-Safe Configuration for your python-projects

    Your specific application configurations should inherit from this 'ConfigModel' class.
    The ConfigModel itself is simply a Pydantic model. Therefore your configuration-definition is a pydantic BaseModel.
    Pydantic will do all the hard stuff (python type-hints, validating data, when assigning to a field,...).

    ConfigModel loads data from different sources and merge them together, in that order:
      source-code, toml-file(s), json-file(s), cli-parameter, env-vars
    So, a config-fields defined in a toml-file can be overwritten by the cli-params and the env-vars.

    Basic Usage:
    ```
    # main.py #
    from pydantic import BaseModel, Field
    from typesave_config import ConfigModel

    class MyAppConfig(ConfigModel):
        username: str = Field(..., description="The username to log in")  # load (secret) field vie cli-interface
        password: str
        url: str = Field("https://example.com/", description="Optional: the url to log in")
        verbose: bool = True

    conf = MyAppConfig.load(toml_files=['myconf.toml'])
    if conf.verbose:
        print(f"login user {conf.username} at {conf.url}")
    ```

    You can can load any missing (or secret) configuration-data before runtime, by using the
    cli-interface (env-vars and/or cli-arguments). The cli-interface is case insensitiv.

    $ TSC_USERNAME="root" python main.py --tsc_password="123"
    """

    @classmethod
    def _get_attr_metadata(
        cls, model: Type[BaseModel], _indent: int = 0, _path: str = ""
    ) -> list[ConfigAttrMetadata]:
        field_seperator = "__"
        f = []
        for name, info in sorted(model.model_fields.items()):
            f_model = model.__name__
            f_name = str(name)
            f_rawtype = info.annotation
            f_type = info.annotation
            f_description = str(info.description) + " " + str(f_type)
            f_fullname = (
                f"{_path}{field_seperator}{f_name}" if _path else f_name
            )  # full-path outflatted (pompts.name ==> prompts__name)
            f_default = info.default if info.default is not None else None

            # Extract the type name as a string
            if hasattr(f_type, "__name__"):
                type_name = f_type.__name__  # type: ignore
            elif hasattr(f_type, "__origin__") and f_type.__origin__ is list:  # type: ignore
                list_args = get_args(f_type)
                if list_args:
                    list_type = list_args[0]
                    type_name = (
                        f"list[{list_type.__name__}]"
                        if hasattr(list_type, "__name__")
                        else f"list[{str(list_type)}]"
                    )
                else:
                    type_name = "list"
            else:
                type_name = str(f_type).replace("<class '", "").replace("'>", "")

            f.append(
                ConfigAttrMetadata(
                    model=f_model,
                    name=f_name,
                    fullanme=f_fullname,
                    raw_type=f_rawtype,
                    type=type_name,
                    description=f_description,
                    default=f_default,
                )
            )
            # If the field type is a Pydantic model, recursively process it
            if hasattr(f_type, "model_fields"):
                f += cls._get_attr_metadata(f_type, _indent + 1, f_fullname)  # type: ignore
            # Handle List[PydanticModel]
            if hasattr(f_type, "__origin__") and f_type.__origin__ is list and get_args(f_type):  # type: ignore
                list_type = get_args(f_type)[0]
                if hasattr(list_type, "model_fields") and list_type != model:
                    f += cls._get_attr_metadata(list_type, _indent + 1, f_fullname)
        return f

    @classmethod
    def _get_possible_cli_argsname(cls) -> list[str]:
        """Returns: list of lower(fullname), that are allowed in cli-interface"""
        r:list[str] = []
        for m in cls.get_metadata():
            if m.type in ["str", "int", "float", "bool"]:  # skip lists and dicts
                r.append(m.fullanme)
        return r
    
    @classmethod
    def _add_flat_key_value_to_nested_dict(
        cls, target_dict: dict, full_name: str, value: Any, field_seperator: str
    ):
        """
        Reconstructs a nested dictionary structure from a flat key (e.g., "prompts__name") and a value.
        Updates the target_dict in place.
        """
        parts = full_name.split(field_seperator)
        current_level = target_dict
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                # Last part is the actual key for the value
                current_level[part] = value
            else:
                # Nested part, ensure it's a dictionary
                if part not in current_level or not isinstance(
                    current_level[part], dict
                ):
                    current_level[part] = {}
                current_level = current_level[part]

    @classmethod
    def _deep_merge(cls, dict1, dict2):
        """Deepply merges two dicts together"""
        for key, value in dict2.items():
            if (
                key in dict1
                and isinstance(dict1[key], dict)
                and isinstance(value, dict)
            ):
                dict1[key] = cls._deep_merge(dict1[key], value)
            else:
                dict1[key] = value
        return dict1

    @classmethod
    def _set_frozen(cls, model: Type[BaseModel]) -> None:
        """
        Sets the "frozen-mode" recursivly foreach pydantic ConfigModel/BaseModel or list of BaseModels
        This provents overwriting the configuration after loading the data. Instead it raises a pydantic_core.ValidationError
        """
        for name, info in sorted(model.model_fields.items()):
            f_type = info.annotation
            # handle pydantic-model
            if hasattr(f_type, "model_fields"):
                cls._set_frozen(f_type)  # type: ignore
            # handle List[PydanticModel]
            if hasattr(f_type, "__origin__") and f_type.__origin__ is list and get_args(f_type):  # type: ignore
                list_type = get_args(f_type)[0]
                if hasattr(list_type, "model_fields") and list_type != model:
                    cls._set_frozen(list_type)

        logging.debug(f"🔧 set {model.__name__} to frozen/readonly")
        model.model_config = {"frozen": True}  # set this BaseModel to readonly/frozen

    @classmethod
    def _load_toml(cls, filenames: list[str]) -> dict:
        toml_config = {}
        for toml_file in filenames:
            toml_file_path = Path(toml_file)
            if toml_file_path.exists():
                try:
                    with open(toml_file_path, "rb") as f:
                        toml_config = tomllib.load(f)
                    logging.debug(f"🔧 data loaded from toml: {toml_file_path}")

                except Exception as e:
                    logging.debug(
                        f"🔧 failed Loading data from toml-file {toml_file_path}, skipped {e}"
                    )
            else:
                logging.debug(f"🔧 toml-file '{toml_file_path}' not found, skipped")
        return toml_config

    @classmethod
    def _load_json(cls, filenames: list[str]) -> dict:
        json_config = {}
        for json_file in filenames:
            json_file_path = Path(json_file)
            if json_file_path.exists():
                try:
                    with open(
                        json_file_path, "r"
                    ) as f:  # Open in text mode ("r") for JSON
                        json_config = json.load(f)
                    logging.debug(f"🔧 data loaded from json: {json_file_path}")

                except Exception as e:
                    logging.debug(
                        f"🔧 failed Loading data from json: {json_file_path}, skipped {e}"
                    )
            else:
                logging.debug(f"🔧 json-file '{json_file_path}' not found, skipped")
        return json_config

    @classmethod
    def _load_cli(cls, prefix: str, sep: str) -> dict:
        # Loads configuration from CLI arguments using a manual parser. Allowing only "--key=value" (key is case-insensitive) pattern.
        cli_prefix = "--" + prefix.lower()
        cli_possible_argnames = cls._get_possible_cli_argsname()
        loaded_args: list[str] = []
        unknown_args: list[str] = []
        
        cli_config = {}
        args_to_parse = sys.argv[1:]
        for arg in args_to_parse:
            match_equal = re.match(r"^(--[^=]+)=(.+)$", arg)  # only allow pattern --key=value
            if match_equal: 
                arg_key = match_equal.group(1)  # --tsc_user__username
                arg_value = match_equal.group(2)
                key_fullname = arg_key[len(cli_prefix):] # user__username
                field_name = next((key for key in cli_possible_argnames if key.lower() == key_fullname.lower()), None)
                if not field_name is None: # user_UserName or None
                    cls._add_flat_key_value_to_nested_dict(cli_config, field_name, arg_value, sep)
                    loaded_args.append(arg_key)
                else:
                    unknown_args.append(arg)
            else:
                # Treat any other format as unknown/unsupported
                unknown_args.append(arg)

        logging.debug(f"🔧 data loaded from cli-arguments (prefix='{prefix}'): [{', '.join(loaded_args)}], irgnored [{', '.join(unknown_args)}]")
        return cli_config


    @classmethod
    def _load_env(cls, prefix: str, sep: str) -> dict:
        # loads env-vars. not case-sensitive!
        env_config = {}
        cli_possible_argnames = cls._get_possible_cli_argsname()
        prefix_upper = prefix.upper()
        loaded_env_vars = []

        # TODO: dotenv
        # from dotenv import load_dotenv
        # if hasattr(cls, 'use_dotenv') and cls.use_dotenv: # Placeholder for how 'use_dotenv' might be accessed
        #     load_dotenv()

        # check only possible env-vars: cli-interface accepts only base-types (str, int,..)
        for fn in cli_possible_argnames:
            env_name = prefix_upper + fn.upper()
            env_value = os.getenv(env_name)
            if env_value is not None:  # skip unset env-var
                loaded_env_vars.append(env_name)
                cls._add_flat_key_value_to_nested_dict(env_config, fn, env_value, sep)
        logging.debug(f"🔧 data loaded from env (prefix='{prefix}'): [{', '.join(loaded_env_vars)}]")
        return env_config

    @classmethod
    def print_help(cls):
        """
        Prints out help (i.e. all fields and their type, description)
        """
        m = cls.get_metadata()
        for a in m:
            s = f"{a.name} / {a.fullanme}\n"
            s += f"{a.description}\ntype={a.type} | default={a.default}"
            print(s)

    @classmethod
    def get_metadata(cls) -> list[ConfigAttrMetadata]:
        """
        Returns a flat List of all/nested defined config fields.
        """
        return cls._get_attr_metadata(cls)

    @classmethod
    def load(
        cls: Type[TConfigModel],
        toml_files: list[str] = ["conf.toml"],
        json_files: list[str] = [],
        load_env: bool = True,
        load_cli: bool = True,
        data: dict = {},
        readonly: bool = True,
        prefix: str = "TSC_",
    ) -> TConfigModel | None:
        """
        Load and merges configurations settings from different sources, in that order:
            source-code , toml-file, json-file, cli-parameter, env-vars.

        Returns:
            ConfigModel: A new configuration instance, preloaded and validated by pydantic. Or None, if validation had errors.

        Parameters:
            toml_files: TOML files to load; don't use TOML if list is empty.
            json_files: JSON files to load; don't use JSON if list is empty.
            load_env:   If True, use the enviroment-variables.
            load_cli:   If True, use the cli-arguments.
            data:       Load data directly from a python dict within the source-code.
            readonly:   Returned configuraion is read-only/frozen, if True.
            prefix: Prefix for env-vars and cli-args. Hint: don't use an empty prefix for env-vars.
        """
        field_seperator: str = "__"
        pydantic_model: Type[TConfigModel] = cls

        toml_config = cls._load_toml(toml_files) if toml_files else {}
        json_config = cls._load_json(json_files) if json_files else {}
        cli_config = cls._load_cli(prefix, field_seperator) if load_cli else {}
        env_config = cls._load_env(prefix, field_seperator) if load_env else {}

        try:
            merged_config = {}
            # merged_config = {**data, **toml_config, **json_config, **cli_config, **env_config}
            merged_config = cls._deep_merge(merged_config, data)
            merged_config = cls._deep_merge(merged_config, toml_config)
            merged_config = cls._deep_merge(merged_config, json_config)
            merged_config = cls._deep_merge(merged_config, cli_config)
            merged_config = cls._deep_merge(merged_config, env_config)

            loaded_configmodel = pydantic_model(**merged_config)
            if readonly:
                cls._set_frozen(cls)

            logging.info(
                f"🔧 {pydantic_model.__name__}(ConfigModel) loaded as {'readonly' if readonly else 'writeable'}"
            )
            return loaded_configmodel
        except ValidationError as e:
            err_str = []
            for ve in e.errors():
                err_str.append(
                    f"field '{str(ve["loc"][0])}' {str(ve['type']).capitalize()},{str(ve["msg"])}"
                )
            logging.warning(
                f"🔧 Loading {pydantic_model.__name__}(ConfigModel) faild with {e.error_count()} error(s): [{"|".join(err_str)}]"
            )
        return None
