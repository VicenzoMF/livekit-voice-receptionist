# Bright Smile Dental — AI phone receptionist

A real-time voice agent built with the LiveKit Agents SDK (Python). It answers the phone for a dental clinic, plus a small React admin UI to configure it.

> **Status: draft.** The sections marked _TODO_ are not finished yet.

- **Agent:** "Sarah", the receptionist. She checks availability, books appointments, transfers to a human and ends the call.
- **Admin UI:** edit the system prompt, name, greeting and voice, and turn the business tools on or off. Changes apply on the next call.
- **Bonus: evals.** An automated test suite of agent behavior, run against the real LLM. See [Evals](#bonus-evals).

---

## Setup (< 5 min)

Requirements: Python 3.13 + [uv](https://docs.astral.sh/uv/), Node 20+, and a free [LiveKit Cloud](https://cloud.livekit.io) project.

```bash
# 1. keys: LiveKit Cloud -> Settings -> API Keys
cd backend
cp .env.example .env.local      # fill LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET
uv sync

# 2. admin API (terminal 1, from backend/)
uv run fastapi dev api/main.py

# 3. voice agent (terminal 2, from backend/)
uv run python -m voice.main console   # talk with your mic in the terminal
# or: uv run python -m voice.main dev # then use the LiveKit Agents Playground

# 4. admin UI (terminal 3)
cd admin
npm install
npm run dev                     # http://localhost:5173

# 5. evals (from backend/)
uv run pytest -v
```

The three LiveKit keys also cover STT, LLM and TTS through LiveKit Inference, so you don't need OpenAI, Deepgram or Cartesia keys.

---

## What I built and why

_TODO: write up the full reasoning._ Key decisions so far:

- **Stack:** Deepgram nova-3 (STT), gpt-4.1-mini (LLM), Cartesia sonic-3 (TTS), Silero VAD and the LiveKit turn detector, all through LiveKit Inference.
- **Config is reloaded on every call.** `entrypoint` reads `data/config.json` when a call starts, so a save in the admin applies to the next call without a restart. Calls already in progress keep the config they started with.
- **Operators control personality and business tools; the platform controls safety.** The prompt, persona and scheduling tools can be edited in the UI. `SAFETY_RULES`, `transfer_to_human` and `end_call` are always added in code and can't be removed from the UI.
- **Two-layer emergency guardrail.**
  1. A deterministic regex runs in `on_user_turn_completed`, *before* the LLM. On a match it speaks a fixed 911 message and stops the LLM with `StopResponse`.
  2. `SAFETY_RULES` in the prompt is the second layer, for phrasings the regex misses. If the regex check itself crashes, the call falls back to layer 2 instead of going silent.
- **One `build_agent(config)` factory** ([backend/voice/factory.py](backend/voice/factory.py)) is shared by real calls and by the evals, so the tests run against the same agent that takes calls.
- **Voice is a dropdown, not a free-text ID.** An invalid Cartesia voice ID doesn't crash anything: the TTS just produces no audio and the call goes silent. The API rejects unknown IDs (422), and every ID in [core/voices.py](backend/core/voices.py) was checked by synthesizing real audio.
- **The greeting uses `session.say`**, with no LLM round-trip, so the caller hears something immediately.

## What I like about LiveKit

_TODO: expand._ LiveKit Inference (one set of keys gives a working pipeline in minutes), the turn detector, false-interruption resume, the built-in `EndCallTool`, `prewarm`, and a testing API (`session.run()` + `judge`) that made the evals bonus cheap to build.

## What I'd improve with more time

_TODO: expand._
- A real scheduling API behind the same tool interface (the mock is in-memory and resets on restart), and a real SIP transfer.
- A small classifier instead of the emergency regex.
- Audio-level evals (TTS → STT round trip) to cover what text evals can't.
- An LLM-driven simulated caller for multi-turn evals.

---

## Bonus: evals

```bash
cd backend
uv run pytest -v            # each test once, ~25 s
uv run pytest --count 5     # each test 5x: measures flakiness, not just pass/fail
```

**Why evals.** The other bugs in the log below were found by calling the agent by hand, and each prompt fix risked breaking another rule. On a platform where operators edit prompts in a UI, evals are the safety net: they check that the agent still behaves after someone changes the prompt. The tests load the *saved* config, so a bad prompt edit makes them fail.

**What's covered** (runs against the real LLM through a text-only `AgentSession`):

| File | What it checks |
|---|---|
| [test_scheduling.py](backend/tests/test_scheduling.py) | Right tool with the right date; never says "09:00"; no booking before the read-back; doesn't ask again for details already given; books with the right arguments after a yes |
| [test_guardrails.py](backend/tests/test_guardrails.py) | Emergency regex (unit tests); the hook blocks the LLM; the LLM layer alone still says 911; no medical advice; declines off-topic questions without transferring; asks before transferring for billing; transfers right away when asked for a person; prompt injection |
| [test_voice_style.py](backend/tests/test_voice_style.py) | No markdown or lists; short enough for one phone turn; phone number read digit by digit; LLM-as-judge on "sounds like a receptionist" |

Deterministic checks (tool name and arguments, regex on the spoken text) are used wherever possible. LLM-as-judge is used only for things a regex can't check ("didn't give medical advice"). When a test fails, it prints the full conversation.

**Result:** 110/110 with `--count 5`. That's 22 checks × 5 runs; 7 of the 22 are regex unit tests that don't call the LLM.

### Why this is hard for voice

- **Non-determinism.** The same input takes different paths: sometimes the read-back comes in turn 1, sometimes in turn 2. Tests have to check *invariants* ("never books before reading the number back") instead of exact text. A test that passes once proves little; two of the bugs below only showed up with `--count`.
- **Text evals skip the voice layer.** They don't exercise STT errors ("five one nine" transcribed as "519" or "fifty-one nine"), interruptions, barge-in or turn detection. They also skip `on_user_turn_completed`: `session.run()` calls `generate_reply()` directly, so the emergency hook never runs in text evals (bug 7 below).
- **Multi-turn needs a caller that reacts.** A fixed script ("yes", "yes", "yes") answers "what's your phone number?" with "yes". The booking test uses a tiny simulated caller that answers what the agent actually asked.
- **"Sounds natural" is subjective**, so it needs an LLM judge or a human ear.

---

## Bug log

Real problems found while building, and how each was fixed. Bugs 1–5 were found by calling the agent by hand; bugs 6–10 were found by the evals.

| # | Found by | Bug | Root cause | Fix |
|---|---|---|---|---|
| 1 | Manual call | With the scheduling tools disabled, the agent said "let me check, one moment", went silent, then **made up** "Tuesday at 3 PM is available" (that slot was taken). | Nothing in the prompt forbade stating facts that didn't come from a tool. | `SAFETY_RULES`: "only state availability from a tool result" and "never say you'll check something unless you call a tool in that same turn". |
| 2 | Manual call | "What's the capital of France?" → the agent **transferred the call** to a human. | Prompt rules competed with each other: "transfer when you can't help" also matched off-topic questions. | Split into three cases: off-topic → decline; clinic-related with no tool → *ask*, then transfer; asks for a person or an emergency → transfer now. This conflict is the reason the evals exist. |
| 3 | Manual call | The agent went **silent** on an emergency. | A typo in the guardrail (`self.sessions`) raised an exception inside the hook. | The hook now fails safe (try/except falls back to the LLM layer) and has unit tests. |
| 4 | Manual call | Asked to "repeat slower", the agent switched to formatted digits like "519-940-30966". | It only had a digit-by-digit rule for the first time it said a number. | The prompt now says to always use spoken digits, including on repeats. |
| 5 | Manual call | The agent skipped saying the chosen time out loud before asking for details. | On the phone the caller has no scrollback, so every step has to be confirmed aloud. | The booking flow now confirms the time out loud. |
| 6 | Evals | About 40% of the time, "next Friday" → the agent asked the caller **"what date is next Friday?"** | The LLM only got "Today is Sunday, November 22" and had to do the date math itself; gpt-4.1-mini hedges when unsure. | `build_agent` adds a 14-day calendar ("Friday, November 27 = 2026-11-27") to the prompt. A lookup table instead of math: 3/5 → 15/15. |
| 7 | Evals | The emergency test passed, but the **regex guardrail never ran**. | `session.run()` → `generate_reply()` skips `on_user_turn_completed`, which only runs on the real audio turn path. The test passed only because layer 2 (`SAFETY_RULES`) answered correctly. | Each layer now has its own test: the hook is called directly and must raise `StopResponse`, and a separate test checks that the LLM alone still says 911. |
| 8 | Evals | The agent thought a US number, "519 555 1234", was **incomplete** ("you started with five one nine…"). | The phone example in the prompt had **11 digits** (a Brazilian format), so the model learned that a full number has 11 digits. | A 10-digit US example, plus "US numbers have ten digits". |
| 9 | Evals | About 60% of the time, the agent **asked again** for the phone number or name the caller had already given ("can I have your phone number again?", "can you spell your name?"). | Step 4 of the booking flow was an unconditional order: "Ask for their full name, then their phone number." | Step 4 is now conditional: ask only for what's missing, never ask to repeat or spell; the read-back is the double-check. 13/20 → 20/20. |
| 10 | Evals | The booking test failed about 20% of the time even when the agent behaved correctly. | **A bug in the test:** the scripted caller answered "yes, that's correct" to "what's your phone number?". | A small simulated caller that answers what was asked. Separate tests now measure the agent bug (9) and the flow. |
| 11 | Evals | The agent said "you said **519 555 1234**?", with numerals in the spoken text. | Same family as bug 4: digits leaking into the TTS text, which would be read as "five hundred nineteen…". | Covered by an assertion (no 3+ digit runs in speech). It hasn't reappeared since the fix for bug 9. Next step would be a TTS text transform as a hard guarantee. |

---

## Project layout

```
backend/
  api/main.py           FastAPI: GET/PUT /api/config, GET /api/tools, GET /api/voices
  core/config.py        AgentConfig (Pydantic) + JSON load/atomic save
  data/config.json      the config the admin UI edits
  voice/main.py         LiveKit entrypoint (session, silence handling, greeting)
  voice/factory.py      build_agent(config): shared by calls and evals
  voice/assistant.py    Receptionist agent + emergency hook
  voice/guardrails.py   emergency regex + SAFETY_RULES
  voice/tools/          scheduling (mock), transfer_to_human
  tests/                evals
admin/                  React + Vite admin UI
```
