import datetime as dt
import json

from livekit.agents.voice.run_result import RunResult


def next_weekday(weekday: int) -> dt.date:
  """Next occurrence of a weekday (0 = Monday ... 4 = Friday), never today."""
  today = dt.date.today()
  days_ahead = (weekday - today.weekday()) % 7 or 7
  return today + dt.timedelta(days=days_ahead)


def tool_calls(result: RunResult) -> dict[str, dict]:
  """Tool name -> parsed arguments, for every tool the agent called in this turn."""
  return {
    ev.item.name: json.loads(ev.item.arguments or "{}")
    for ev in result.events
    if ev.type == "function_call"
  }


def spoken_text(result: RunResult) -> str:
  """Everything the agent said in this turn, i.e. what would go to TTS."""
  return " ".join(
    ev.item.text_content or ""
    for ev in result.events
    if ev.type == "message" and ev.item.role == "assistant"
  )
