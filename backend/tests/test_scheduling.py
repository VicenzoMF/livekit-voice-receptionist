import re

from tests.helpers import next_weekday, spoken_text, tool_calls

FRIDAY = next_weekday(4).isoformat()

GIVES_EVERYTHING = (
  "I want a cleaning next Friday at eleven AM. "
  "My name is John Smith and my number is 519 555 1234."
)


async def test_checks_availability_for_requested_day(session):
  result = await session.run(user_input="Hi, can I come in for a cleaning next Friday?")

  calls = tool_calls(result)
  assert "check_availability" in calls, "agent offered times without checking availability"
  assert calls["check_availability"]["date"] == FRIDAY


async def test_never_speaks_times_as_numerals(session):
  result = await session.run(user_input="What times do you have next Friday?")

  said = spoken_text(result)
  assert "check_availability" in tool_calls(result)
  # the tool returns "09:00, 11:00..." - the agent must turn that into "nine AM"
  assert ":" not in said, f"TTS would read the time as digits: {said!r}"


async def test_does_not_book_before_read_back(session):
  # caller gives everything at once - the agent still has to read it back first
  result = await session.run(user_input=GIVES_EVERYTHING)

  assert "book_appointment" not in tool_calls(result), "booked without the caller confirming"


ASKS_FOR_PHONE = re.compile(r"(your|the) (full |complete )?(phone )?(number|digits)\b.*\?", re.I)
ASKS_FOR_NAME = re.compile(r"(your|the) (full )?name\b.*\?", re.I)


def reads_back_phone(said: str) -> bool:
  return "five five five" in said.lower()


def asks_for_phone(said: str) -> bool:
  # "can you confirm your number as five one nine..." is a read-back, not a re-ask
  return bool(ASKS_FOR_PHONE.search(said)) and not reads_back_phone(said)


def asks_for_name(said: str) -> bool:
  return bool(ASKS_FOR_NAME.search(said)) and "john smith" not in said.lower()


def caller_reply(agent_said: str) -> str:
  """A tiny simulated caller: answers what the agent actually asked.

  A fixed script ("yes", "yes", "yes") is not a realistic caller - if the
  agent asks for the phone number, a real person repeats it.
  """
  if asks_for_phone(agent_said):
    return "It's 519 555 1234."
  if asks_for_name(agent_said):
    return "John Smith."
  return "Yes, that's correct."


async def test_does_not_ask_again_for_details_already_given(session):
  # Callers hate repeating themselves. Everything is given in the first turn.
  result = await session.run(user_input=GIVES_EVERYTHING)
  for _ in range(2):
    said = spoken_text(result)
    assert not asks_for_phone(said), f"asked for the phone number again: {said!r}"
    assert not asks_for_name(said), f"asked for the name again: {said!r}"
    assert not re.search(r"\d{3}", said), f"number as numerals, TTS reads 'five hundred...': {said!r}"
    if "book_appointment" in tool_calls(result):
      break
    result = await session.run(user_input="Yes, that's correct.")


async def test_books_after_caller_confirms(session):
  # The path varies run to run: sometimes the agent reads everything back
  # right away, sometimes it confirms the time first and reads back on the
  # next turn. What must hold: it reads the phone number back BEFORE booking,
  # and books with the right data once the caller says yes.
  result = await session.run(user_input=GIVES_EVERYTHING)
  read_back = False
  for _ in range(4):
    assert "book_appointment" not in tool_calls(result), "booked before reading back"
    said = spoken_text(result)
    read_back = read_back or reads_back_phone(said)
    result = await session.run(user_input=caller_reply(said))
    if "book_appointment" in tool_calls(result):
      break

  calls = tool_calls(result)
  assert "book_appointment" in calls, "caller kept confirming but nothing was booked"
  assert read_back, "booked without reading the phone number back"
  args = calls["book_appointment"]
  assert args["date"] == FRIDAY
  assert args["time"] == "11:00"
  assert args["phone_number"] == "5195551234"
  assert "john smith" in args["patient_name"].lower()
