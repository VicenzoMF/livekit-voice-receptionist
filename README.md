# Bright Smile Dental — AI phone receptionist

A real-time voice agent built with the LiveKit Agents SDK (Python). It answers the phone for a dental clinic, plus a small React admin UI to configure it.

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

### The use case: a dental clinic receptionist

I picked a receptionist because it covers the three kinds of tools a phone agent needs:
- **looking something up:** `check_availability`;
- **taking an action with side effects:** `book_appointment`;
- **routing the caller:** `transfer_to_human` and `end_call`.

A dental clinic also brings a real safety problem. Callers describe symptoms, ask whether something is "normal" and occasionally have a real emergency. The guardrail work is about real risk, not a checkbox.

### A typical call

1. Sarah greets the caller and asks what the visit is for and which day works.
2. She checks availability and offers at most three times. When the caller picks one, she confirms it out loud.
3. She collects the name and phone number, asking only for what's missing.
4. She reads everything back in one sentence and books only after a "yes".

Besides booking:
- Anything clinic-related she can't do, like billing or records: she asks first, then transfers.
- Off-topic questions: she declines and steers back to the clinic.
- "Bye": she ends the call.

### Voice is not text

The caller has no screen and no scrollback, and everything the LLM writes gets spoken. Most of the work went into this:

- **Short turns and one question at a time.** A paragraph that reads fine in a chat is 20 seconds of monologue on the phone.
- **Write for the ear.**
  - Times like "two thirty", not "14:30"; dates like "Tuesday the twenty-fourth", not "2026-11-24".
  - Phone numbers in spoken digit groups, including when the caller asks to repeat them.
  - No markdown or lists, since TTS would read the symbols aloud.
  - The evals check these rules (no `:` in spoken times, no 3+ digit runs).
- **Confirm every step out loud.** On the phone, the only way the caller knows the agent got it right is to hear it. That's why the booking flow ends with a full read-back before booking.
- **Never leave silence.** Before calling a tool, the agent says something like "let me check that for you" in the same turn. The greeting uses `session.say`, so it plays right away without waiting on the LLM.
- **Handle the silent caller.** If the caller goes quiet (`user_state_changed` → `away`), Sarah asks "are you still there?" once, then says goodbye and hangs up.
- **Turn detection matters more than the LLM.** The LiveKit turn detector model tells a pause in the middle of a sentence from the end of a turn. In one test call it waited about 3 s while I paused mid-sentence, instead of the usual ~0.5 s, so Sarah didn't cut me off.

### Architecture decisions

- **Stack:** Deepgram nova-3 (STT), gpt-4.1-mini (LLM), Cartesia sonic-3 (TTS), Silero VAD and the LiveKit turn detector, all through LiveKit Inference. One set of keys, and every model can be swapped by changing a string. gpt-4.1-mini is fast enough for voice; its weaknesses (date math, multi-step instructions) showed up in the evals and were fixed in the prompt and context, not by switching to a bigger model.
- **Config is reloaded on every call.** `entrypoint` reads `data/config.json` when a call starts, so a save in the admin applies to the next call without a restart. Calls already in progress keep the config they started with: switching a persona's voice mid-call would be worse than waiting. A JSON file with an atomic write (`os.replace`) is enough for one user; with a database only `load_config`/`save_config` would change.
- **Operators control personality and business tools; the platform controls safety.**
  - The prompt, persona and scheduling tools can be edited in the UI.
  - `SAFETY_RULES`, `transfer_to_human` and `end_call` are always added in code and can't be removed from the UI.
  - On a multi-tenant platform, a customer editing their prompt must not be able to delete the emergency instructions or the way out to a human.
- **Two-layer emergency guardrail.**
  1. A deterministic regex runs in `on_user_turn_completed`, *before* the LLM. On a match it speaks a fixed 911 message and stops the LLM with `StopResponse`. This is fast and predictable, and the LLM can't talk its way around it.
  2. `SAFETY_RULES` in the prompt is the second layer, for phrasings the regex misses. If the regex check itself crashes, the call falls back to layer 2 instead of going silent.
- **Adding a business tool is two lines.** Write a `@function_tool` and add it to `TOOL_REGISTRY` in [voice/tools/\_\_init\_\_.py](backend/voice/tools/__init__.py). The API lists it, the UI shows a checkbox with the docstring's first paragraph as its description, and `build_agent` enables it when it's checked.
- **One `build_agent(config)` factory** ([backend/voice/factory.py](backend/voice/factory.py)) is shared by real calls and by the evals, so the tests run against the same agent that takes calls. It also adds today's date and a 14-day calendar to the prompt (bug 6 below).
- **Tool errors tell the LLM how to recover.** For example, `ToolError("That time was just taken. Check availability again and offer another time.")`. A generic exception would leave the model guessing what to say to the caller.
- **Voice is a dropdown, not a free-text ID.** An invalid Cartesia voice ID doesn't crash anything: the TTS just produces no audio and the call goes silent. The API rejects unknown IDs (422), and every ID in [core/voices.py](backend/core/voices.py) was checked by synthesizing real audio.
- **Mocks where the task allows them.** The schedule is in memory, and the transfer is simulated (it logs a reason and a summary for the staff member, then ends the call). Both keep the tool interface a real integration would use.

### What worked and what didn't

- **Worked:**
  - The two-layer safety design.
  - Spoken-format rules (the agent reliably says "nine AM").
  - Corrections in the middle of a call: the caller fixes a digit and the agent reads the corrected number back.
  - Ending the call on a wrong-number "bye".
- **Didn't work at first:** prompt rules that compete. "Transfer when you can't help" made the agent transfer on "what's the capital of France?". Each fix risked breaking another rule, which is why I chose evals as the bonus. The [bug log](#bug-log) has the full list.

## What I like about LiveKit

- **LiveKit Inference.** One set of keys gives a full STT → LLM → TTS pipeline, and swapping a provider means changing a string like `"cartesia/sonic-3:<voice>"`. It's the main reason setup takes under five minutes.
- **The voice plumbing is done for you,** and well:
  - The turn detector model, on top of VAD.
  - Interruption handling, including resuming after a *false* interruption (a cough or "mm-hm" doesn't kill the agent's sentence).
  - Automatic retry and reconnect when the STT/TTS websocket drops. My network was flaky during development, and calls survived it.
- **Hooks in the right places.** `on_user_turn_completed` runs between the end of the caller's turn and the LLM, exactly where a deterministic guardrail belongs. `StopResponse` cancels the reply cleanly.
- **Small built-ins that save real work:** `EndCallTool`, `session.say`, `prewarm` (VAD is loaded once per process, not per call) and `ToolError`.
- **A testing API in the SDK.** `session.run()`, `result.expect`, `judge()` and `mock_tools` made the evals bonus a matter of hours. Testing voice agents is hard, and having this built in is a strong signal about the framework.

## What I'd improve with more time

- **Real integrations behind the same tool interfaces:**
  - A scheduling API instead of the in-memory mock, which resets on restart and has no concurrency control.
  - A real SIP transfer that passes the summary to the staff member.
- **A safer emergency check.** The regex is English-only and narrow. In production it would be a small, fast classifier still running *before* the LLM, with the regex kept as a backstop.
- **Hard guarantees for spoken format.** A TTS text transform that turns any remaining digits or times in the text into words, instead of trusting the prompt alone (bugs 4 and 11).
- **Latency.** Measure time to first audio per stage (end of turn → LLM first token → TTS first byte) with LiveKit metrics, then try preemptive generation and a filler while slow tools run. During development I saw multi-second gaps, mostly from my network, but I didn't separate that from pipeline time.
- **Evals:**
  - An LLM-driven simulated caller instead of the small rule-based one.
  - Audio-level tests (TTS → STT round trip), to cover what text evals can't: transcription errors, interruptions, turn detection.
  - Running the evals in CI on every prompt change, and showing pass rates in the admin before a prompt is saved.
- **Admin UI:**
  - A "test call" button.
  - A diff and history of prompt versions.
  - A warning when an edited prompt drops a step the evals depend on.

---

## Bonus: evals

```bash
cd backend
uv run pytest -v            # each test once, ~25 s
uv run pytest --count 5     # each test 5x: measures flakiness, not just pass/fail
```

### Why I picked this bonus

The other bugs in the log below were found by calling the agent by hand, and each prompt fix risked breaking another rule. On a platform where operators edit prompts in a UI, evals are the safety net: they check that the agent still behaves after someone changes the prompt. The tests load the *saved* config, so a bad prompt edit makes them fail.

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
