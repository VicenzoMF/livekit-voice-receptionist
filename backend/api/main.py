from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core.voices import VOICES, Voice
from voice.tools import TOOL_REGISTRY
from core.config import AgentConfig, load_config, save_config


app = FastAPI(title="Receptionist Admin API")


class ToolInfo(BaseModel):
  name: str
  description: str

@app.get("/api/config")
def get_config() -> AgentConfig:
  return load_config()

@app.put("/api/config")
def update_config(config: AgentConfig) -> AgentConfig:
  unknown_tools = set(config.enabled_tools) - TOOL_REGISTRY.keys()
  if unknown_tools:
    raise HTTPException(422, f"Unknown tools: {sorted(unknown_tools)}")

  if config.voice not in {v.id for v in VOICES}:
    raise HTTPException(422, f"Unknown voice: {config.voice}")

  save_config(config)
  return config

@app.get("/api/tools")
def list_tools() -> list[ToolInfo]:
  return [
    ToolInfo(name=name, description=tool.info.description.split("\n\n")[0])
    for name, tool in TOOL_REGISTRY.items()
  ]


@app.get("/api/voices")
def list_voices() -> list[Voice]:
  return VOICES