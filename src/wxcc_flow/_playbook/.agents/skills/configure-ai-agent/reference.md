# AI Agent Studio -- Quick Reference

## Agent Goal

Short, concise statement of the agent's overall purpose. Focuses on the end result for the caller.

**Do:** Keep it short, clear, aligned with capabilities. Focus on benefit to the caller.
**Don't:** Include specific details, action names, technical jargon, or multiple unrelated goals.

## Slot Entity Fields

| Field | Notes |
|-------|-------|
| Entity Type | `String` for most values (including phone numbers); `Date` for dates; `Number` for quantities |
| Entity Name | Lowercase underscores: `phone_number`, `preferred_date` |
| Entity Description | Plain language -- tells the LLM what to ask the caller |
| Entity Example | Format hint for the LLM (e.g., `5551234567`, `2026-03-15`) |
| Required | Toggle ON for mandatory fields |

**Phone number = String** (not Number). Using Number breaks leading zeros and formatting.

## Action Description Rules

- Max **1024 characters**
- Reference returned variables in **quotes**: `"first_name"`, `"confirmation_number"` -- WORKS
- **NEVER** use `{{variable_name}}` for Flow Outcomes return data -- returns the literal string. Exception: `{{variable_name}}` works for custom data variables from Flow Designer State Event (see `docs/reference/ai-agent-studio.md` "Custom Data at Session Start").
- Include: when to call, what it needs, what it returns, how to use the data

## Action Name

Use `lowercase_underscores` format. The LLM uses this name to identify the action; the Connect flow is linked via the flow selector dropdown in AI Agent Studio.

## Enable Toggle

Actions must be **ENABLED** (toggle ON) to fire. If OFF, the action silently does not execute. **Most common oversight.**

## Output Variables

AI Agent Studio has **no output variables section**. Outputs come from Flow Outcomes in the Connect flow. Reference those keys in the action description with quotes.

## Welcome Message

Separate field from Instructions. First thing the caller hears. Set under agent configuration, not the Instructions tab.

## Agent Instructions Template

Use markdown headings and lists. Follow this structure:

1. **Identity** — Role definition, tone and demeanor
2. **Context** — Background info, environment details (voice = background noise caveat)
3. **Task** — Sequential steps referencing actions. Forceful language for required actions ("You MUST call...")
4. **Response Guidelines** — Voice: 1-2 sentences, no stacked questions. Digital: bullet lists, numbered steps
5. **Error Handling and Fallbacks** — Clarification prompts, default responses, action failure handling
6. **Guardrails** — Stay in scope, domain-specific restrictions
7. **Examples** (optional) — Sample conversation for complex flows

| Pattern | Example |
|---------|---------|
| Forceful required action | "You MUST call verify_caller before anything else. No exceptions." |
| Timezone conversion | "All times are UTC. Convert to Eastern (subtract 5 hours). Never mention UTC." |
| Clarification prompt | "I didn't catch that, could you please repeat?" |
| Action failure | "I'm having trouble looking that up. Let me transfer you to someone who can help." |
| Conversation pacing | One to two sentences at a time. Don't stack questions. |

## Testing

| Mode | Reliability | Notes |
|------|-------------|-------|
| Chat Preview | Non-deterministic | LLM may skip actions; add forceful language before assuming config issue |
| Voice Preview | More reliable | Test via WxCC Flow Designer with Virtual Agent V2 + CCAI Config |

## CCAI Config (Linking Agent to WxCC)

1. Control Hub > Contact Center > AI Agents > CCAI Configs > New
2. Select deployed agent from dropdown
3. Name the config
4. Use config name in Virtual Agent V2 node in Flow Designer

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Action never fires | Enable toggle OFF | Turn it ON |
| Action never fires (toggle ON) | Name mismatch with Connect flow | Exact case-sensitive match |
| Agent skips required action | LLM non-determinism | "You MUST call..." language |
| Variables as literal strings | Using `{{var}}` syntax | Use quoted names: `"var"` |
| Agent gives wrong time | No timezone note | Add UTC conversion instruction |
| Chat preview unreliable | Expected LLM behavior | Use voice preview instead |
| No greeting | Welcome Message empty | Set Welcome Message field |
| Agent not in CCAI dropdown | Not deployed | Click Deploy first |
| Flow data doesn't reach agent | Notify AI Agent radio button not selected | Verify selected in Flow Settings → Flow Outcomes → Last Execution Status (enabled by default for AI Agent flows) |
