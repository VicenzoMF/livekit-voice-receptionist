from pydantic import BaseModel


class Voice(BaseModel):
  id: str
  name: str


VOICES = [
  Voice(id="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc", name="Default (female, US)"),
]