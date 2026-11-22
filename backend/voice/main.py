from dotenv import load_dotenv
from livekit.agents import AgentServer, AgentSession, JobProcess, JobContext, cli, inference
from livekit.plugins import silero
from core.config import load_config
from voice.tools import TOOL_REGISTRY
import datetime as dt

from voice.assistant import Receptionist
from voice.guardrails import SAFETY_RULES
from voice.tools.call_control import transfer_to_human
from livekit.agents.beta import EndCallTool


load_dotenv(".env.local")

server = AgentServer()

def prewarm(proc: JobProcess) -> None:
  proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
  config = load_config()

  business_tools = [TOOL_REGISTRY[n] for n in config.enabled_tools if n in TOOL_REGISTRY]
  tools = [*business_tools, transfer_to_human, EndCallTool()]

  today = dt.date.today()

  session = AgentSession(
    stt="deepgram/nova-3",
    llm="openai/gpt-4.1-mini",
    tts=f"cartesia/sonic-3:{config.voice}",
    vad=ctx.proc.userdata["vad"],
    turn_handling={"turn_detection": inference.TurnDetector()},
  )

  agent = Receptionist(
    instructions=(
      f"Your name is {config.agent_name}.\n"
      f"Today is {today:%A, %B %d, %Y}.\n\n"
      f"{config.instructions}\n\n"
      f"{SAFETY_RULES}"
    ),
    tools=tools,
  )

  # caller went silent: check in once, then hang up politely
  away_count = 0

  @session.on("user_state_changed")
  def on_user_state_changed(ev) -> None:
    nonlocal away_count
    if ev.new_state == "speaking":
      away_count = 0
      return
    if ev.new_state != "away":
      return

    away_count += 1
    if away_count == 1:
      session.say("Hello? Are you still there?")
    else:
      handle = session.say("I'll let you go for now. Feel free to call back anytime. Goodbye!")
      handle.add_done_callback(lambda _: session.shutdown())  # hang up after speaking

  await session.start(agent=agent, room=ctx.room)
  await session.say(config.greeting)

if __name__ == "__main__":
    cli.run_app(server)