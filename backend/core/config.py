import os
from pathlib import Path

from pydantic import BaseModel, Field



CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "config.json"


DEFAULT_INSTRUCTIONS = """You are the receptionist at Bright Smile Dental, answering the phone.

How you speak:
- This is a phone call. Keep replies to one or two short sentences.
- Never use lists, bullet points, markdown, or emojis. Everything you write is spoken aloud.
- Say times and dates the way people say them: "Tuesday at two thirty", not "14:30".
- Ask one question at a time.
"""

class AgentConfig(BaseModel):
  agent_name: str = "Sarah"
  greeting: str = "Thanks for calling Bright Smile Dental, this is Sarah. How can I help you today?"
  voice: str = "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
  instructions: str = DEFAULT_INSTRUCTIONS
  enabled_tools: list[str] = Field(default_factory=list)

def load_config() -> AgentConfig:
  if not CONFIG_PATH.exists():
    return AgentConfig()
  return AgentConfig.model_validate_json(CONFIG_PATH.read_text(encoding="utf-8"))

def save_config(config: AgentConfig) -> None:
  CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
  tmp = CONFIG_PATH.with_suffix(".json.tmp")
  tmp.write_text(config.model_dump_json(indent=2), encoding="utf-8")
  os.replace(tmp, CONFIG_PATH)