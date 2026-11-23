from pydantic import BaseModel


class Voice(BaseModel):
  id: str
  name: str


# Cartesia sonic-3 voices available through LiveKit Inference
# (https://docs.livekit.io/agents/models/tts/inference/cartesia/).
# Only IDs verified to synthesize audio: an invalid ID makes TTS fail silently
# mid-call, which is why the admin offers a fixed list instead of a free text field.
VOICES = [
  Voice(id="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc", name="Jacqueline (female, US, confident)"),
  Voice(id="a167e0f3-df7e-4d52-a9c3-f949145efdab", name="Blake (male, US, energetic)"),
  Voice(id="f31cc6a7-c1e8-4764-980c-60a361443dd1", name="Robyn (female, Australian, calm)"),
]
