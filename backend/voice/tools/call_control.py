import logging
from typing import Literal

from livekit.agents import RunContext, function_tool

logger = logging.getLogger("receptionist")

TransferReason = Literal[
  "caller_request", "billing", "complaint", "clinical_question", "emergency", "cannot_help"
]



@function_tool
async def transfer_to_human(context: RunContext, reason: TransferReason, summary: str) -> str:
  """Transfer the caller to a human staff member at the front desk.

  Transfer immediately when:
  - The caller asks to speak to a person.
  - There is a possible emergency.

  Transfer only AFTER the caller agrees, when:
  - They need something clinic-related you can't do: billing, complaints, medical records.
  - They ask a clinical question: symptoms, medication, whether something is normal.
  - You failed to understand them twice in a row, or a tool keeps failing.

  Never transfer for questions unrelated to the clinic. Just decline those.

  Args:
  reason: Why the call is being transferred.
  summary: One sentence for the staff member describing what the caller needs.
  """
  logger.info("TRANSFER reason=%s summary=%s", reason, summary)

  context.speech_handle.add_done_callback(lambda _: context.session.shutdown())
  return "Transfer started. In one short sentence, tell the caller you're connecting them to the front desk now."
