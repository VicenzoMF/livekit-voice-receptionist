from dotenv import load_dotenv
from livekit.agents import Agent, AgentServer, AgentSession, JobProcess, JobContext, cli
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from core.config import load_config

load_dotenv(".env.local")

server = AgentServer()

def prewarm(proc: JobProcess) -> None:
  proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
  config = load_config()

  session = AgentSession(
    stt="deepgram/nova-3",
    llm="openai/gpt-4.1-mini",
    tts=f"cartesia/sonic-3:{config.voice}",
    vad=ctx.proc.userdata["vad"],
    turn_handling={"turn_detection": MultilingualModel()},
  )

  agent = Agent(
    instructions=(
      "You are a friendly receptionist at a dental clinic, talking on the phone. "
      "Keep replies short: one or two sentences. Never use lists, markdown or emojis."
      )
  )

  await session.start(agent=agent, room=ctx.room)
  await session.say(config.greeting)

if __name__ == "__main__":
    cli.run_app(server)