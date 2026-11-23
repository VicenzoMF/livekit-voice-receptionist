import re

from tests.helpers import spoken_text

# things that sound broken when read aloud by TTS
MARKDOWN = re.compile(r"[*#`]|^\s*[-•]\s|^\s*\d+\.\s", re.MULTILINE)


async def test_reply_is_short_and_plain_speech(session, llm):
  result = await session.run(user_input="Hi, where are you located and what are your hours?")

  said = spoken_text(result)
  assert not MARKDOWN.search(said), f"markdown/list would be read aloud: {said!r}"
  assert len(said.split()) <= 45, f"too long for one phone turn ({len(said.split())} words)"

  await (
    result.expect.contains_message(role="assistant")
    .judge(llm, intent=(
      "Sounds like a human receptionist on the phone: short, conversational, "
      "gives the address 120 Main Street Suite 4 and hours Monday to Friday 9 to 5."
    ))
  )


async def test_says_phone_number_digit_by_digit(session):
  await session.run(
    user_input=(
      "Book me a cleaning next Friday at eleven AM. "
      "I'm John Smith, 519 555 1234."
    )
  )
  result = await session.run(user_input="Sorry, can you repeat my phone number?")

  said = spoken_text(result)
  assert not re.search(r"\d{3}", said), f"number written as digits, TTS may say 'five hundred': {said!r}"
  assert "five one nine" in said.lower().replace(",", "")
