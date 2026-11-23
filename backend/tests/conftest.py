import pytest
from dotenv import load_dotenv
from livekit.agents import AgentSession, inference

from core.config import load_config
from voice.factory import LLM_MODEL, build_agent
from voice.tools import scheduling

load_dotenv(".env.local")


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
  # expose the test result to fixtures, so `session` can dump the call on failure
  report = yield
  setattr(item, f"rep_{report.when}", report)
  return report


def _transcript(sess: AgentSession) -> str:
  lines = []
  for it in sess.history.items:
    if it.type == "message":
      lines.append(f"{it.role.upper():>9}: {it.text_content}")
    elif it.type == "function_call":
      lines.append(f"{'TOOL':>9}: {it.name}({it.arguments})")
    elif it.type == "function_call_output":
      lines.append(f"{'RESULT':>9}: {it.output}")
    else:
      lines.append(f"{'(' + it.type + ')':>9}")
  return "\n".join(lines)


@pytest.fixture(autouse=True)
def fresh_bookings():
  # bookings live in memory; reset so one test's booking can't leak into another
  scheduling._booked.clear()


@pytest.fixture
async def llm():
  async with inference.LLM(model=LLM_MODEL) as model:
    yield model


@pytest.fixture
async def session(llm, request):
  # text-only session: no STT/TTS/room, user_input goes straight to the LLM.
  # uses the config saved by the admin UI, so a broken prompt fails the evals.
  async with AgentSession(llm=llm) as sess:
    await sess.start(build_agent(load_config()))
    yield sess
    rep = getattr(request.node, "rep_call", None)
    if rep is not None and rep.failed:
      print(f"\n--- conversation ---\n{_transcript(sess)}")
