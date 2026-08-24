# ElevenLabs ConvAI — Latency & Speaking-Speed Playbook

The house reference for making every agent this pipeline builds **fast** — quick to
start speaking, quick between turns, and paced right when it speaks. The architect
skill enforces this by default on every build; each configurator carries the slice
of it that its fields own. Target: **sub-second from end-of-caller-speech to first
agent audio**, per ElevenLabs' own guidance.

## Two different "slow"s — diagnose before tuning

1. **Lag** (response latency): a gap before the agent starts talking. Caused by the
   pipeline below, *not* by the TTS `speed` setting.
2. **Speaking pace**: the agent talks, but too slowly/quickly. That IS the TTS
   `speed` setting (`0.7`–`1.2`, default `1.0`) — a pace lever, not a latency lever.

Never "fix" lag by raising `speed`, and never fix a pace complaint by swapping models.

## The latency chain (and which configurator owns each link)

A turn's total lag ≈ ASR finalization → turn-taking decision → LLM time-to-first-token
→ LLM generation → TTS time-to-first-byte → network/playback. Unlike most systems,
no single link dominates — each contributes within a degree of the others, so total
lag is a **sum of parts** and every link is worth tightening. The diagnostic metric
per link is *time-to-first-output*, not total generation: the LLM's tokens stream
into TTS and TTS audio streams out faster than speech plays back, so LLM latency ≈
time-to-first-token and TTS latency ≈ time-to-first-byte.

Reference budgets per link (ElevenLabs' "Latency in Conversational AI" report) — use
these to spot which link is out of band when diagnosing a slow line: ASR ≈100 ms
after end-of-speech (Whisper-class implementations run 300 ms+) · flash-class LLM
<350 ms TTFT vs 700–1000 ms for heavyweight models · TTS Flash ≈75 ms model time /
≈135 ms e2e TTFB (Turbo ≈250–300 ms) · telephony +200 ms same-region, ~500 ms
cross-region. The levers, roughly biggest first:

| Lever | Fast default | Owner |
|---|---|---|
| LLM model | **House primary: an ElevenLabs-hosted Qwen model** (e.g. Qwen3-30b-a3b — sub-150 ms time-to-first-sentence, and it runs inside ElevenLabs' own stack, so no cross-provider network hop). Resolve the exact model id live from an agent's config (`agents_get`) or the connector tool schema's model enum (not pinned in this repo). Fall back to a flash-class model (`gemini-2.5-flash`) only if the hosted Qwen tier is unavailable or fails the client's quality bar — and use that class for `backup_llm_config`. Reasoning/"thinking" modes OFF for voice — for Qwen specifically, use the **non-thinking/instruct variant** (or thinking explicitly disabled); Qwen's hybrid thinking mode emits `<think>` blocks that add seconds of dead air before the first word. | `elevenlabs-llm-tuning-configurator` |
| Response length | `max_tokens` capped (house default `300`) + a brevity rule in the system prompt. Text length is the biggest hidden spike: a 500-char reply synthesizes 4–6× slower than an 80-char one. | llm-tuning (cap) + `elevenlabs-persona-configurator` (brevity rule) |
| TTS model | `eleven_flash_v2_5` / `eleven_flash_v2` (~75 ms) — ElevenLabs recommends Flash over Turbo (~250–300 ms) in all cases; Multilingual v2 / v3 + `expressive_mode` are quality/expressiveness trades that cost latency. | `elevenlabs-voice-tts-configurator` |
| Prompt size (TTFT) | Lean system prompt (tone/behavior only — facts in KB, per house rule); no large KB docs on `usage_mode: "always"`; lean tool roster (every tool schema rides in the prompt). | persona + knowledge + tools configurators |
| RAG vs prompt-injection | RAG retrieval adds ~250–300 ms per turn but keeps the prompt small; a large KB injected wholesale bloats every turn's TTFT. Small KB → prompt mode; large KB → RAG. Never both worlds' costs (huge `"always"` docs *and* RAG off). | `elevenlabs-knowledge-configurator` |
| Voice choice | Premade/default voices are the low-latency path; professional voice clones (PVC) add latency on Flash/Turbo models — flag the trade before picking one for a latency-sensitive line. | `elevenlabs-voice-tts-configurator` |
| Tool round-trips | A blocking webhook/server tool holds the whole turn for its full round-trip; slow endpoints = dead air. Tight timeouts, fast endpoints, async/webhook patterns where the reply doesn't depend on the result — and for calls that must block, a **pre-tool verbal acknowledgment** ("Let me check that for you") drafted into the tool's usage contract, so the wait reads as engagement instead of dead air. | `elevenlabs-tools-escalation-configurator` |
| Turn-taking timing | `turn_timeout`/VAD tuning changes *perceived* wait before the agent decides to speak. Tune only after the links above are fast — timing tweaks can't hide a slow LLM, and over-tightening makes the agent interrupt callers. | `elevenlabs-runtime-qa-configurator` |
| Streaming knobs | `conversation_config.tts` may expose `optimize_streaming_latency` (0–4; quality-for-speed trade, deprecated on the raw TTS API). Confirm presence/shape live via `agents_get` before drafting it — house unverified-schema rule. | `elevenlabs-voice-tts-configurator` |
| Telephony & geography | A phone call adds ~200 ms even same-region; a cross-region hop (e.g. a number homed outside the callers' country, forcing the audio through its base region's phone network) can add ~500 ms that no config lever can claw back. Match the number's region to the caller base when assigning; treat an out-of-region number on a latency-sensitive line as a flag-worthy trade. | `elevenlabs-runtime-qa-configurator` (phone-number assignment) |

## Fast-by-default build posture (what the architect enforces)

On every new build, and on every latency complaint against an existing agent, check:

- [ ] LLM is the house primary — an ElevenLabs-hosted Qwen model (non-thinking variant) — or a justified flash-class alternative; reasoning/thinking off; `max_tokens` capped (≈300); backup LLM in the same speed class
- [ ] TTS `model_id` is a Flash model unless multi-language/expressiveness genuinely requires otherwise (and then the trade is stated, not silent)
- [ ] System prompt is lean and carries a brevity rule; business facts live in the KB
- [ ] No large KB doc on `usage_mode: "always"`; RAG on for large KBs, off for small ones
- [ ] Tool roster is only what the requirements call for; server tools have tight timeouts
- [ ] `tts.speed` left at `1.0` unless the client asked for a pace change (0.7–1.2; extremes degrade quality)
- [ ] Phone number (if telephony is in scope) is homed in the callers' region; blocking tools carry a pre-tool verbal acknowledgment in their usage contract

## Symptom → lever routing (for the reviewer/engineer loop)

| Complaint | First suspects (in order) |
|---|---|
| "Long pause before it answers" | LLM model/reasoning · RAG on unnecessarily · prompt bloat (KB `"always"`, huge prompt, fat tool schemas) · TTS model · turn timing |
| "It talks too slowly / too fast" | `tts.speed` (pace, not latency) |
| "Goes silent mid-call after a question" | blocking tool round-trip · LLM generation length |
| "Feels slow to react but then talks fine" | turn/VAD timing — but rule out LLM TTFT first |
| "Rambles forever" | `max_tokens` + prompt brevity rule (also a latency win — shorter text synthesizes far faster) |
| "Every call lags, but the fast-by-default checklist passes" | telephony geography — where is the number homed vs. where do callers dial from? A cross-region number adds ~500 ms before any config lever matters |

Sources: ElevenLabs docs — [Models](https://elevenlabs.io/docs/overview/models),
[Latency optimization](https://elevenlabs.io/docs/eleven-api/guides/how-to/best-practices/latency-optimization),
[Speed control](https://elevenlabs.io/docs/eleven-agents/customization/voice/speed-control),
[RAG](https://elevenlabs.io/docs/agents-platform/customization/knowledge-base/rag),
[How do you optimize latency for Conversational AI?](https://elevenlabs.io/blog/how-do-you-optimize-latency-for-conversational-ai),
[ElevenLabs-hosted LLMs](https://elevenlabs.io/blog/elevenlabs-hosted-llms).
