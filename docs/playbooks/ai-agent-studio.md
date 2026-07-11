# Webex AI Agent Studio Playbook

## Overview

This playbook covers how to create, configure, and deploy an autonomous AI agent in Webex AI Agent Studio, from first login through linking it to WxCC.

---

## 1. Access AI Agent Studio

1. Log in to **Webex Control Hub** (admin.webex.com)
2. Navigate to **Contact Center > AI Agents**
3. Click **AI Agent Studio** — opens in a new tab

---

## 2. Create a New Agent

1. Click **Create Agent**
2. Select **Autonomous** (for LLM-driven conversation) or **Scripted** (for decision-tree flows)
   - This project uses **Autonomous**
3. Fill in:
   - **Name**: e.g., `Scheduling Agent`
   - **Description**: brief description for admin reference
4. Click **Create**

---

## 3. Configure Agent Instructions

Under the **Instructions** tab:

### System Prompt / Goal
Write the agent's goal and operating constraints. Be explicit about:
- What the agent is for (e.g., "You are a scheduling assistant for [Organization]...")
- What actions the agent MUST call and when (use forceful language to prevent LLM skipping)
- What the agent should NOT do (domain-specific restrictions)
- Escalation triggers ("If the caller asks for a human agent, transfer the call")

### Timezone Handling
If your database returns UTC timestamps, add explicit instruction:
> "All times returned from the database are in UTC. You MUST convert to [local timezone] before telling the caller any times."

### Forceful Action Triggers
To prevent LLM from skipping required first steps:
> "You MUST call [lookup_action] before anything else, even if you think you already have the caller's information."

---

## 4. Add Slot Entities

Slot entities define the variables the agent collects from the caller and passes to actions.

Navigate to **Slots** tab → **Add Slot**

### Entity Fields
| Field | Notes |
|-------|-------|
| Entity Type | `String` for most values including phone numbers; `Date` for date inputs |
| Entity Name | lowercase underscores: `phone_number`, `preferred_date` |
| Entity Description | Plain language for the LLM — tells it what to ask |
| Entity Example | Example value the LLM uses as a hint |
| Required | Toggle ON for entities the action cannot run without |

### Phone Number Entity
- Type: **String** (not Number — leading zeros and formatting)
- Example: `5551234567`

---

## 5. Add Actions

Each action maps to one Webex Connect flow. Navigate to **Actions** tab → **Add Action**.

### Action Fields

**Name**: match the Connect flow event name exactly (e.g., `lookup_customer`)

**Description**: The LLM reads this to decide when and how to call the action. Include:
- When to call it ("Call this action when you need to look up a customer...")
- What it returns ("Returns 'customer_first_name', 'account_status'...")
- Variable references use quotes: `"customer_first_name"` — **confirmed working**
- `{{variable_name}}` syntax does NOT work — avoid

**Input Entities**: Select which slot entities this action requires

**Configure AI Agent Event**: configured in **Webex Connect** (Receive node), not here in AI Studio. See connect-flows.md §7

**Enable toggle**: must be switched ON — easy to forget; action will silently not fire if off

### Standard Action Template

```
Action Name: lookup_customer

Description:
Call this action when you need to look up a customer record.
Requires: phone_number (collected from caller)
Returns: "customer_first_name", "customer_last_name", "account_status"
Use "customer_first_name" to greet the caller by name after this action completes.

Input Entities: phone_number (required)

Configure AI Agent Event Sample JSON:
{
  "phone_number": "5551234567"
}
```

---

## 6. Configure AI Agent Event (Sample JSON)

**Note:** This is configured in **Webex Connect** (Receive node), not in AI Agent Studio.

This JSON tells Webex Connect what variable shape the action sends. Required for every action.

Rules:
- One key per slot entity the action uses
- Use realistic example values (actual test data works well)
- Configure this in the Connect flow's **Receive node** → **Configure AI Agent Event**

---

## 7. Output Variables

AI Agent Studio does not have an output variables section. Outputs are returned via **Flow Outcomes** from the Connect flow.

The agent reads returned values by the key names set in the Connect flow's Flow Outcomes node. Reference those keys in the action description with quotes (e.g., `"confirmation_number"`).

---

## 8. Test the Agent

### Chat Preview
- Use the **Preview** panel in AI Agent Studio
- Note: chat preview is non-deterministic — LLM may skip actions unpredictably
- Add forceful language in instructions if an action doesn't fire

### Voice Preview
- Voice preview is more reliable and closer to production behavior
- Test via WxCC Flow Designer using the Virtual Agent V2 node with your CCAI Config

---

## 9. Deploy the Agent

1. In AI Agent Studio, click **Deploy** (or **Publish**)
2. Note the **Agent ID** — used when creating the CCAI Config

---

## 10. Create a CCAI Config

This links the deployed AI agent to WxCC:

1. **Control Hub > Contact Center > AI Agents > CCAI Configs > New**
2. Select your deployed agent
3. Name the config (e.g., `Scheduling_CCAI`)
4. Save

Use this CCAI Config name in the **Virtual Agent V2** node in WxCC Flow Designer (see wxcc-setup.md).

---

## 11. Welcome Message

The Welcome Message is a **separate field** in AI Agent Studio (not part of the instructions). Set it under the agent's configuration. This is the first thing the caller hears.

```
Thanks for calling [Organization]! I can help you with [list of capabilities]. What's the best phone number for your account?
```

---

## 12. Agent Instructions — Example Template

```
You are a friendly, professional virtual assistant for [Organization]. You help callers with [list of capabilities — e.g., scheduling, account lookups, order status]. Keep it natural, like a real phone conversation. One to two sentences at a time.

REQUIRED FIRST ACTION:
You MUST call lookup_customer before anything else. EVERY conversation starts by identifying the caller via their phone number. No exceptions. Don't use their name until you've actually gotten it back from the system via "customer_first_name."

If their number doesn't match any account, say: "I'm not finding an account with that number. Let me connect you with someone who can help." Then transfer.

ONCE YOU HAVE THEIR RECORD:
Use their first name right away — "Hey Sarah, thanks for calling!" Then ask what they need help with. Let them lead.

[Add action-by-action guidance for each action your agent supports. For each one, describe:
- When to call it
- What to say before/after calling it
- How to present the returned data naturally
- What to do if the action fails or returns no results]

Example — scheduling flow:
1. Ask what service/item they need → call get_item_info → confirm details and any prep instructions
2. Ask what date works → call check_availability → present open times naturally ("I've got a 10 AM and a 2:30 in the afternoon")
3. Confirm all details before booking → call create_order → read back confirmation number

IMPORTANT ABOUT TIMES: All timestamps from the database are in UTC. Convert to [local timezone, e.g., US Eastern — subtract 5 hours] before telling the caller. Never mention UTC — callers don't need to hear that.

ESCALATION:
If you can't help or the caller asks for a person, say: "Let me connect you with someone who can help." Then transfer.

GROUND RULES:
- Never reveal internal IDs or database values (UUIDs, etc.) to the caller.
- Never guess — if you don't know, say so. "I'm not sure about that" is always better than making something up.
- Confirm details before making changes (booking, cancelling, updating).
- [Add domain-specific restrictions — e.g., "Don't give medical/legal/financial advice."]

HOW TO SOUND ON THE PHONE:
- Keep it short. One or two sentences at a time. This is a phone call, not an email.
- Don't stack multiple questions in one breath.
- It's OK to say "Let me check on that" or "One sec" — it sounds human.
- If someone seems unsure or confused, slow down. Repeat the important part. Ask if they have questions.
- If they change their mind or go in a different direction mid-conversation, just roll with it.
- Always wrap up with: "Anything else I can help with?"
- Sign off warm: "Thanks for calling [Organization], Sarah. Have a great day!"
```

---

## 13. Troubleshooting

| Symptom | Check |
|---------|-------|
| Action never fires | Action enable toggle OFF — turn it ON |
| Agent skips a required action | Strengthen instruction language: "You MUST call..." |
| Variables returned as literal strings | Using `{{variable}}` syntax — use quoted name in description instead |
| Agent gives wrong time | Missing UTC→local timezone conversion note in instructions |
| Chat preview unpredictable | Expected — use voice preview for reliable testing |
