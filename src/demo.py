import logging
import sys
from datetime import datetime, date
from pydantic import BaseModel, Field

from rich.console import Console
from rich.pretty import Pretty
#from rich.markdown import Markdown

from typesafe_config import ConfigModel


logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')


# --- define application specific configuration  ---
class AppConfigPrompt(BaseModel):
    """Configuration sub-table prompt"""
    name: str = Field(..., description="The name or identifier for the prompt.")
    value: int = Field(..., description="A numerical value associated with the prompt.")

class AppConfigUser(BaseModel):
    """Configuration sub-table user"""
    UserName: str = Field('anonym', description="The username.")
    PassWord: str = Field(..., description="The password. required.")

class AppConfig(ConfigModel):
    """Configuration main-table"""
    project_name: str = Field(..., description="The name of the Python project.")
    version: str = Field(..., description="The name of the Python project.")
    user: AppConfigUser = Field(..., description="Current logged in user..")
    database_url: str = Field(..., description="The connection string for the database.")
    debug_mode: bool = Field(..., description="Indicates if debug mode is enabled.")
    allowed_hosts: list[str] = Field(..., description="A list of allowed hostnames for the application.")
    port: int = Field(..., description="The port number on which the application will run.")
    weight: float = Field(..., description="The weight of the logged in user.")
    prompts: list[AppConfigPrompt] = Field(..., description="A list of prompt configurations.")
    dt_field: datetime = Field(datetime(2024,12,31,12,34))
    d_field: date = Field(datetime(2024,12,30))
# --- / define application specific configuration  ---

conf = AppConfig.load(toml_files=['test_conf.toml', 'a.toml'],
                      #json_files=['a.json', 'b.json'],
                      data={'version':'0.1 alpha'},
                      load_cli=True,
                      load_env=True,
                      readonly=True,
                      )

if not conf:
    #AppConfig.print_help()
    sys.exit(1)
console = Console()


#print(conf)
console.print(Pretty(conf))
#print(conf.user.username, conf.user.password)
#conf.project_nameversion="OVERWRITTEN"
#conf.user.password="OVERWRITTEN"
#conf.prompts[0].name="OVERWRITTEN"
#conf.print_config()
#conf.print_help()
