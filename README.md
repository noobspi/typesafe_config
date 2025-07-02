# TypeSafe-Config - ConfigModel

TypeSafe-Config is an easy-to-use python appplication/script configuration system with fully support for python's typehints used by your IDE.
Thanks to [pydantic](https://docs.pydantic.dev/latest/#why-use-pydantic) with ideas from [FastAPI](https://fastapi.tiangolo.com/) and [dynaconf](https://www.dynaconf.com/) ❤️

## Basic Usage

```python
from pydantic import BaseModel, Field
from typesave_config import ConfigModel

class MyAppConfig(ConfigModel):
    url: str # required
    verbose: bool = True # optional

conf = MyAppConfig.load(toml_files=['myconf.toml'])
if conf.verbose:
    print(f"use url {conf.url}")
```

## How it works

🔧 **1. Declare your configuration** by inheriting from `ConfigModel`. Use nested pydantic-models for nested configuration data (aka toml-tables).

```python
from pydantic import BaseModel, Field
from typesave_config import ConfigModel

class MyAppConfig_Login(BaseModel):
    username: str
    password: str = Field(..., min_length=6)

class MyAppConfig(ConfigModel):
    login: MyAppConfig_Login
    url: str 
    verbose: bool = True
```

🔧 **2. Load data from different sources** and merge them carefuly together (source-code, toml-files, json-files, cli-parameter, env-variables, in this order).
A defined, or secretly missing, value in a config-file can be overwritten by the cli-interface.

```python
conf = MyAppConfig.load(toml_files=['myconf.toml'])
```

🔧 **3. Access key/value pairs the fully pydantic/typed way**, including intellisense support in your favorite IDE, like vscode or PyCharm. Your configuration is basically a [pydantic-model](https://docs.pydantic.dev/latest/concepts/models/), so you are free to specify each [field](https://docs.pydantic.dev/latest/api/fields/) with defaults, description, validating conditions and much more. All the hard stuff will be handled by pydantic's [BaseModel](https://docs.pydantic.dev/latest/api/base_model/).

```python
if conf.verbose:
    print(f"user {conf.login.username} logged in")
conf.url="https://a.com/" # raises error at runtime, when set to be readonly (the default)
```

🔧 **4. Use the cli-interface for secreets** and other data, that should not be included in the config-files. Think of database-connections, username, password, api-keys, etc. Hint: `list`and `dict` themselves can't be set by the cli-interface 🤷. However, nested pydantic-models are supported 😄

```bash
TSC_LOGIN__USERNAME="root" python main.py --tsc_login__password="12345678"
```
