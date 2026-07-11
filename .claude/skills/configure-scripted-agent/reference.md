# Scripted AI Agent Studio — Quick Reference

## AI Engines

| Engine | Best For | Notes |
|--------|----------|-------|
| **Swiftmatch Pro 2.0** | Most use cases | LLM-enhanced intent matching; requires intent descriptions |
| **Swiftmatch Pro 1.0** | Simple bots, no LLM dependency | Simpler matching without LLM |
| **MindMeld** | Entity roles (origin/destination) | Supports entity role disambiguation |

## Entity Types

| Type | Use For | Notes |
|------|---------|-------|
| Custom list | Finite set of values | Add all values with synonyms |
| Regex | Pattern-based input | e.g., `[A-Z]{3}\d{6}` for confirmation codes |
| Digits | Fixed-length numeric input | Set expected length |

**Entity type cannot be changed after creation.** Delete and recreate if wrong.

## Response Variable Syntax

| Syntax | Source | Example |
|--------|--------|---------|
| `${entity.name}` | Collected slot values | `${entity.appointment_date}` |
| `${extra_params.name}` | Flow message parameters | `${extra_params.customer_name}` |
| `${eventStore.name}` | Custom Event data (voice) | `${eventStore.confirmation_number}` |

## Intent Configuration Checklist

| Field | Required? | Notes |
|-------|-----------|-------|
| Intent Name | Yes | e.g., `book_appointment` |
| Description | Yes (Pro 2.0) | Helps NLU distinguish similar intents |
| Utterances | Yes (3 min, 10+ recommended) | Use Generate variants for more |
| Slots | If entities needed | Link entity, set Required, Retries, Response |
| Entry Contexts | If chained | Context values required for intent to match |
| Exit Contexts | If chained | Context values activated when intent matches; set Duration (turns) |
| Reset slots | Optional | Toggle ON to clear slot values after completion |
| End conversation | Optional | Toggle ON for terminal intents |

## Context Flow

- **Entry context**: Intent only matches when this context is active
- **Exit context**: Intent activates this context when matched
- **Duration**: Number of conversational turns the context stays active
- Chain intents by setting one intent's exit context as another's entry context

## System Responses

| Response | Default | Customize? |
|----------|---------|-----------|
| Welcome message | Generic greeting | Yes — set from design doc |
| Fallback message | "I didn't understand" | Yes |
| Partial message | "Did you mean..." | Yes |
| Agent handover | "Connecting you..." | Yes |

## AI Engine Tuning

| Setting | Default | When to Change |
|---------|---------|---------------|
| Fallback threshold | Platform default | Lower if fallback fires too often |
| Partial match threshold | Platform default | Adjust based on testing |
| Spellcheck in inference | OFF | Turn ON for text channels |
| Expand contractions | OFF | Turn ON (handles "don't" → "do not") |
| Prioritize slot filling | OFF | Turn ON if entity extraction > intent switching |

## CCAI Config (Linking Agent to WxCC)

1. Control Hub > Contact Center > Tenant Settings > Integrations > Features
2. Create new Contact Center AI Config
3. Select published scripted agent
4. Name the config
5. Use config name in Virtual Agent V2 node (Flow Designer) or AI Agent node (Connect)

## Channel Wiring

| Channel | Platform | Node | Agent Type Setting |
|---------|----------|------|-------------------|
| Voice | Flow Designer | Virtual Agent V2 | "Webex AI Agent Scripted" |
| Digital | Webex Connect | AI Agent | Agent Type: Scripted, Method: Process Message |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Intent not matching | Too few utterances | Add 10+ utterances; use Generate variants |
| Similar intents confused | Missing intent descriptions (Pro 2.0) | Add clear, unique descriptions |
| Entity type wrong | Type locked after creation | Delete and recreate entity |
| Slot not collected | Entity not linked as Required slot | Click +Link, toggle Required ON |
| Context chain breaks | Exit context duration too short | Increase duration (number of turns) |
| Custom Event not firing (voice) | Response type not Custom Event on Voice | Add Custom Event response for Voice channel |
| template_key not found (digital) | Response missing template key | Set template key in Response Designer |
| Agent not in CCAI dropdown | Not published | Click Publish first |
