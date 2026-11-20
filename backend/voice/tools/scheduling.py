import datetime as dt

from livekit.agents import ToolError, function_tool

CLINIC_SLOTS = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"]

_booked: dict[str, set[str]] = {}

def _taken_slots(day: dt.date) -> set[str]:
  key = day.isoformat()
  if key not in _booked:
    _booked[key] = {"10:00", "15:00"} if day.day % 2 == 0 else {"09:00", "14:00"}
  return _booked[key]

def _parse_day(date: str) -> dt.date:
  try:
    day = dt.date.fromisoformat(date)
  except ValueError:
    raise ToolError(f"'{date}' is not a valid date. USE YYYY-MM-DD.")
  if day < dt.date.today():
    raise ToolError("That date is in the past.")
  if day.weekday() >= 5:
    raise ToolError("The clinic is closed on weekends. Offer a weekday instead.")
  return day


@function_tool
async def check_availability(date: str) -> str:
   """Check which appointment times are open on a given day.

    Call this before offering any time to the caller. Never guess availability.

    Args:
        date: The day to check, in YYYY-MM-DD format.
    """
   day = _parse_day(date)
   free = [s for s in CLINIC_SLOTS if s not in _taken_slots(day)]
   if not free:
     return f"No openings on {day:%A, %B %d}. Suggest another day."
   return f"Open times on {day:%A, %B %d}: {', '.join(free)}."

@function_tool
async def book_appointment(
  patient_name: str, phone_number: str, date: str, time: str, reason: str
) -> str:
  """Book an appointment.

    Only call this AFTER you have read back the date, time, name and phone number
    to the caller and they confirmed everything is correct.

    Args:
        patient_name: Caller's full name.
        phone_number: Caller's phone number, digits only.
        date: Appointment day, in YYYY-MM-DD format.
        time: Appointment time in 24h HH:MM format, e.g. 14:00.
        reason: Short reason for the visit, e.g. "cleaning" or "toothache".
    """
  day = _parse_day(date)
  if time not in CLINIC_SLOTS:
    raise ToolError(f"{time} is not a valid slot. Valid slots: {', '.join(CLINIC_SLOTS)}.")
  taken = _taken_slots(day)
  if time in taken:
    raise ToolError("That time was just taken. Check availability again and offer another time.")

  taken.add(time)
  print(f"[BOOKED] {patient_name} | {phone_number} | {day} {time} | {reason}")
  return f"Booked {patient_name} on {day:%A, %B %d} at {time}."