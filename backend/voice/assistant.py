import logging

from livekit.agents import Agent, StopResponse, llm

from voice.guardrails import EMERGENCY_MESSAGE, is_emergency

logger = logging.getLogger("receptionist")

class Receptionist(Agent):
  async def on_user_turn_completed(
      self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
  ) -> None:
    # runs after the caller and before the llm
    text = new_message.text_content or ""
    try:
      emergency = is_emergency(text)
    except Exception:
      # fail safe: if the check breaks, the LLM (with SAFETY_RULES) still answers
      logger.exception("guardrail check failed; falling back to LLM")
      return

    if emergency:
      logger.warning("EMERGENCY detected: %r", text)
      self.session.say(EMERGENCY_MESSAGE, allow_interruptions=False)
      raise StopResponse()  # outside the try: it's a signal, not an error

