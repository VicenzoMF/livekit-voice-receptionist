import datetime as dt

from livekit.agents.beta import EndCallTool

from core.config import AgentConfig
from voice.assistant import Receptionist
from voice.guardrails import SAFETY_RULES
from voice.tools import TOOL_REGISTRY
from voice.tools.call_control import transfer_to_human

# shared with the evals so tests run against the same model as real calls
LLM_MODEL = "openai/gpt-4.1-mini"

def _calendar(today: dt.date, days: int = 14) -> str:
  # small LLMs are bad at date math ("next Friday" -> asks the caller what date
  # that is). Give them a lookup table instead of making them compute it.
  lines = [
    f"- {d:%A, %B %d} = {d.isoformat()}"
    for d in (today + dt.timedelta(days=i) for i in range(1, days + 1))
  ]
  return "\n".join(lines)


def build_agent(config: AgentConfig) -> Receptionist:
  """Build the agent from config. Used by the real call and by the evals."""
  business_tools = [TOOL_REGISTRY[n] for n in config.enabled_tools if n in TOOL_REGISTRY]
  today = dt.date.today()

  return Receptionist(
    instructions=(
      f"Your name is {config.agent_name}.\n"
      f"Today is {today:%A, %B %d, %Y} ({today.isoformat()}).\n"
      "Upcoming days, use this to resolve 'tomorrow', 'next Friday', etc. "
      "Never ask the caller which date they mean if you can look it up here. "
      "'Next <weekday>' means the first one in this list.\n"
      f"{_calendar(today)}\n\n"
      f"{config.instructions}\n\n"
      f"{SAFETY_RULES}"
    ),
    tools=[*business_tools, transfer_to_human, EndCallTool()],
  )
