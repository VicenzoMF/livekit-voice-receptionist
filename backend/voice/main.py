from dotenv import load_dotenv
from livekit.agents import AgentServer, AgentSession, JobProcess, JobContext, cli, inference
from livekit.plugins import silero
from core.config import load_config
from voice.factory import LLM_MODEL, build_agent


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
    llm=LLM_MODEL,
    tts=f"cartesia/sonic-3:{config.voice}",
    vad=ctx.proc.userdata["vad"],
    turn_handling={"turn_detection": inference.TurnDetector()},
  )

  agent = build_agent(config)

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