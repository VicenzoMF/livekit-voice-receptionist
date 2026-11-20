from .scheduling import check_availability, book_appointment

TOOL_REGISTRY = {
  "check_availability": check_availability,
  "book_appointment": book_appointment
}