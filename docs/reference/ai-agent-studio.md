# Webex AI Agent Studio -- Platform Reference (Autonomous Agents)

<!-- ref-tag: ai-agent-studio-v1 -->

> This reference covers **autonomous** agents. For **scripted** agents, see `ai-agent-studio-scripted.md`.

## Access

1. Log in to **Webex Control Hub** (admin.webex.com)
2. Navigate to **Contact Center > AI Agents**
3. Click **AI Agent Studio** -- opens in a new tab

---

## Agent Types

| Type | Description | Use When |
|------|-------------|----------|
| **Autonomous** | LLM-driven conversation; agent decides what to say and when to call actions | Natural language interactions, complex workflows |
| **Scripted** | Intent-entity-response architecture; NLU classifies input, agent returns pre-authored responses (see `ai-agent-studio-scripted.md`) | Deterministic responses, compliance-sensitive, high-volume/cost-sensitive deployments |

---

## Creating an Agent

1. Click **Create Agent**
2. Select agent type (Autonomous or Scripted)
3. Fill in:
   - **Name**: descriptive name for the agent
   - **Description**: brief description for admin reference
4. Click **Create**

---

## Agent Goal

The Agent Goal field is a short, concise statement of the agent's overall purpose. It focuses on the end result or benefit for the caller.

**Do's:**
- Keep it short and concise
- Focus on the overall function or purpose
- Consider the end result or benefit for the user
- Use clear and concise language
- Ensure the goal aligns with the actions and capabilities of the agent

**Don'ts:**
- Don't include specific details like locations, dates, or user information
- Don't mention particular actions or implementation methods
- Don't use technical jargon or complex terminology
- Don't use overly long or complicated goal statements
- Don't include multiple unrelated goals in a single prompt
- Don't use ambiguous or vague language

---

## Agent Instructions (System Prompt)

The Instructions tab defines the agent's personality, capabilities, and constraints. The LLM reads this on every turn. Use markdown headings and lists for best results.

**Tip:** Add instructions after configuring actions and testing the agent. Adding instructions after testing enhances efficiency and accuracy.

### Instructions Template

#### 1. Identity

- **Role Definition**: Define the persona and expertise. "You are [Name/Role], a [description] for [Organization]."
- **Tone and Demeanor**: Specify friendly, formal, or casual. Match the organization's brand voice.

#### 2. Context

- **Background Information**: Relevant context (e.g., "This is a customer support line for scheduling and account inquiries").
- **Environment Details**: System constraints (e.g., "The caller is on voice and may have background noise which impacts transcription quality").

#### 3. Task

Break down the overall task into specific, sequential steps. Reference the actions at each step that will be used to fulfill the task.

- Step 1: What happens first (e.g., identity verification)
- Step 2: What the agent can do next
- Step N: Additional capabilities

For each step: when to call the action, what it returns, how to use the data.

**Forceful language**: The LLM is non-deterministic and may skip required actions. Use:
- "You MUST call [action_name] before anything else."
- "Do NOT proceed without first calling [action_name]."
- "EVERY conversation starts with [action_name]. No exceptions."

Weak phrasing like "you should" or "try to" will be ignored intermittently.

**Timezone handling**: If the database stores timestamps in UTC, add explicit conversion:
> "All times returned from the database are in UTC. You MUST convert to [Local Timezone] (subtract/add N hours) before telling the customer any time. Never mention UTC to the customer."

#### 4. Response Guidelines

- **Formatting Rules**: For voice: one to two sentences at a time, don't stack multiple questions. For digital: bullet lists for options, numbered steps.
- **Language Style**: Natural filler ("Let me check on that", "One moment"). Confirm before committing -- read back details and wait for "yes". Wrap up: "Anything else I can help with?" Sign off warm: "Thanks for calling, [Name]. Have a great day!" Handle mid-conversation pivots gracefully.

#### 5. Error Handling and Fallbacks

- **Clarification Prompts**: "I didn't catch that, could you please repeat?"
- **Default Responses**: "I'm sorry, I didn't understand. Can you try rephrasing?"
- **Action Failures**: "I'm having trouble looking that up. Let me transfer you to someone who can help."

#### 6. Guardrails

Instruct the agent to respond only in the context of the goal and not entertain unrelated queries. Include domain-specific restrictions (no unauthorized advice, no internal IDs, etc.).

#### 7. Examples (Optional)

Add a sample conversation between the caller and the agent for better prompt adherence. Most useful for complex or nuanced flows.

---

## Welcome Message

The Welcome Message is a **separate field** from the Instructions. It is the first thing the caller hears when they connect.

Set it under the agent's configuration (not in the Instructions tab).

Example:
```
Thanks for calling! I can help you with account inquiries, placing orders, checking status, or general questions. How can I help you today?
```

---

## Slot Entities

Slot entities define the variables the agent collects from the caller and passes to actions.

Navigate to **Slots** tab > **Add Slot**

### Entity Fields

| Field | Notes |
|-------|-------|
| **Entity Type** | `String` for most values including phone numbers; `Date` for date inputs; `Number` for numeric quantities |
| **Entity Name** | Lowercase underscores: `phone_number`, `preferred_date` |
| **Entity Description** | Plain language for the LLM -- tells it what to ask the caller |
| **Entity Example** | Example value the LLM uses as a format hint |
| **Required** | Toggle ON for entities the action cannot run without |

### Phone Number = String (NOT Number)

Phone numbers must be entity type **String**, not Number. Using Number causes issues with leading zeros, formatting, and length validation.

---

## Actions

Each action maps to one Webex Connect flow. Navigate to **Actions** tab > **Add Action**.

### Action Fields

**Name**: Must match the Connect flow's Receive node Event Name exactly (case-sensitive). Example: `lookup_customer`

**Description**: The LLM reads this to decide when and how to call the action. Include:

- When to call it: "Call this action when you need to look up a customer..."
- What it returns: "Returns 'first_name', 'last_name', 'account_status'..."
- How to use the returned data: "Use 'first_name' to greet the customer by name."

**Input Entities**: Select which slot entities this action requires.

**Configure AI Agent Event**: This is configured in **Webex Connect** (Receive node), not in AI Agent Studio. See `docs/reference/webex-connect.md` for details.

**Enable toggle**: Must be switched ON for the action to fire.

### Referencing Returned Variables in Action Description

- Use **quoted variable names**: `"first_name"`, `"confirmation_number"` -- CONFIRMED WORKING
- The LLM reads the description and knows to use these variable names from the Flow Outcomes response

### What Does NOT Work for Flow Outcomes Data

- `{{variable_name}}` syntax in action descriptions — returns the literal string `{{variable_name}}` instead of the value when referencing **Flow Outcomes return data**. Use quoted names instead: `"first_name"`, `"confirmation_number"`.

> **Important distinction:** `{{variable_name}}` DOES work for **custom data variables** injected at session start via Flow Designer State Event settings. See [Custom Data at Session Start](#custom-data-at-session-start-voice-only) below. The syntax fails only when referencing data returned by Flow Outcomes.

### Enable Toggle -- Most Common Oversight

Actions must be **ENABLED** (toggle ON) to fire. If the toggle is OFF, the action silently does not execute -- no error, no log, no indication. This is the single most common reason an action fails to fire.

---

## Configure AI Agent Event (Sample JSON)

**Note:** Despite being referenced during AI Studio action setup, this JSON is configured in **Webex Connect** — in the Receive node of the action's flow. See `docs/reference/webex-connect.md` for the full details.

This JSON tells Connect what variable shape the action sends. Required for every action.

### Rules

- One key per slot entity the action uses
- Use realistic example values
- Keys must match entity names exactly
- Configure this in the Connect flow's Receive node, not in AI Agent Studio

### Example

```json
{
  "phone_number": "5551234567"
}
```

---

## Output Variables

AI Agent Studio does **not** have an output variables section. Outputs are returned to the agent via **Flow Outcomes** from the Webex Connect flow.

The agent reads returned values by the key names set in the Connect flow's Flow Outcomes node. Reference those keys in the action description with quotes (e.g., `"confirmation_number"`).

---

## Custom Event Fulfillment (Voice Only)

Autonomous agents have two fulfillment paths. The standard path uses Webex Connect flows (Receive → HTTP Request → Flow Outcomes). The alternative uses **custom event fulfillment** — the agent exits to Flow Designer for fulfillment, then Flow Designer returns the result via State Event.

**Channel support:** Voice channel only. Not available on digital channels.

**Use case:** PCI-compliant fulfillment where sensitive payment data must stay in Flow Designer and never pass through the AI agent or Webex Connect.

### Configure in AI Agent Studio

1. Navigate to the **Actions** tab > create or edit an action
2. In the **Fulfillment** section, select **"Set custom logic for fulfillment"**
3. The action will now exit to Flow Designer instead of triggering a Connect flow

### Flow Designer Side

When the agent calls this action, the Virtual Agent V2 activity exits:
- **StateEventName** = the action name
- **MetaData** = JSON with the collected slot values

The Flow Designer flow:
1. Parses `VirtualAgentV2.MetaData` for the input data
2. Routes on `VirtualAgentV2.StateEventName` (use a Case activity if multiple actions use custom fulfillment)
3. Executes the fulfillment logic (HTTP Request, database call, etc.)
4. Sets `event_name` and `event_data_string` flow variables with the result
5. Routes back to the Virtual Agent V2 activity, which sends the State Event to the agent

This is the same State Event resume mechanism used for scripted agent voice fulfillment. See `docs/reference/flow-designer-patterns.md` § Scripted Agent Fulfillment Pattern for the full activity chain — the pattern is identical for autonomous agents using custom event fulfillment.

### When to Use Custom Event Fulfillment vs. Connect Flows

| Factor | Connect Flows (standard) | Custom Event Fulfillment |
|--------|--------------------------|--------------------------|
| **PCI/compliance** | Data passes through Connect | Data stays in Flow Designer |
| **Build effort** | Need a separate Connect flow per action | Fulfillment logic in the existing Flow Designer flow |
| **Reusability** | Same Connect flow works for voice and digital | Voice only |
| **Debugging** | Connect flow debug logs | Flow Designer activity logs |
| **When to choose** | Default for most actions | PCI requirements, or when all actions need Flow Designer logic anyway |

---

<!-- SYNC: also update docs/reference/ai-agent-studio-scripted.md (Welcome Message / custom data mentions) when changing this section -->
## Custom Data at Session Start (Voice Only)

Developers can pass data from Flow Designer to an autonomous AI agent at the beginning of a session, before the agent speaks. This enables personalized welcome messages, dynamic instructions per customer, and optimized agent behavior.

**Channel support:** Voice channel only. Not available on digital channels.

### How It Works

1. In WxCC Flow Designer, configure the **Virtual Agent V2** activity's **State Event** settings
2. Leave the **Event Name** column blank (this signals session-start data, not a named event)
3. Enter custom data key-value pairs in the **Event Data** column (e.g., `customer_name` = `{{CallerName}}`)
4. The agent receives these as session-level variables accessible via `{{variable_name}}` syntax

### Where Custom Data Variables Can Be Used

| Location | Example |
|----------|---------|
| **Agent Goal** | "Help {{customer_name}} with their account" |
| **Welcome Message** | "Hi {{customer_name}}, thanks for calling!" |
| **Instructions** | "The caller is calling from {{calling_number}}. Use this to look up their account." |
| **Action Description** | "Call this when {{customer_name}} needs to check their order status" |
| **Slot Description** | "The customer's phone number is {{calling_number}}" |

### Example

A Flow Designer flow sets two custom data variables before the Virtual Agent V2 activity:
- `customer_name` = result of a CRM lookup by ANI
- `calling_number` = `{{NewContact.ANI}}`

The agent's Welcome Message uses them: "Hi {{customer_name}}, thanks for calling! I can see you're calling from {{calling_number}}. How can I help?"

### Custom Data vs. Flow Outcomes Variables

| Feature | Custom Data (`{{variable}}`) | Flow Outcomes (quoted names) |
|---------|------------------------------|------------------------------|
| **Set by** | Flow Designer State Event settings | Connect Flow Outcomes node |
| **When available** | Session start (before agent speaks) | After an action completes |
| **Syntax in AI Studio** | `{{variable_name}}` | `"variable_name"` (quoted in description) |
| **Scope** | Entire session | Per-action return |
| **Where it works** | Goal, Welcome Message, Instructions, Action descriptions, Slot descriptions | Action descriptions only |

> **Key rule:** `{{variable_name}}` works for custom data. It does NOT work for Flow Outcomes data. If you see literal `{{variable_name}}` in agent responses, check whether you're referencing custom data (correct syntax) or Flow Outcomes data (use quoted names instead).

---

<!-- SYNC: also update docs/reference/ai-agent-studio-scripted.md (Testing section) when changing this section -->
## Testing

### Chat Preview

- Use the **Preview** panel in AI Agent Studio
- Chat preview is **non-deterministic** -- the LLM may skip actions unpredictably
- If an action doesn't fire in chat preview, add forceful language before assuming a config issue

### Voice Preview

- Voice preview is **more reliable** and closer to production behavior
- Test via WxCC Flow Designer using the Virtual Agent V2 node with your CCAI Config

---

<!-- SYNC: also update docs/reference/ai-agent-studio-scripted.md (Deployment section) when changing this section -->
## Deploying the Agent

1. In AI Agent Studio, click **Deploy** (or **Publish**)
2. Note the **Agent ID** -- used when creating the CCAI Config

---

<!-- SYNC: also update docs/reference/ai-agent-studio-scripted.md (Deployment section) when changing this section -->
## CCAI Config (Linking Agent to WxCC)

The CCAI Config links the deployed AI agent to Webex Contact Center:

1. **Control Hub > Contact Center > AI Agents > CCAI Configs > New**
2. Select your deployed agent from the dropdown
3. Name the config descriptively
4. Save
5. Use this CCAI Config name in the **Virtual Agent V2** node in WxCC Flow Designer

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Action never fires | Action enable toggle is OFF | Turn the toggle ON |
| Action never fires (toggle is ON) | Action name doesn't match Connect flow event name | Ensure exact case-sensitive match |
| Agent skips a required action | LLM non-determinism | Strengthen instruction language: "You MUST call..." |
| Variables returned as literal strings | Using `{{variable}}` syntax to reference Flow Outcomes data | Use quoted variable names for Flow Outcomes data: `"variable_name"`. Note: `{{variable}}` DOES work for custom data variables from State Event — see Custom Data section. |
| Agent gives wrong time | Missing timezone conversion note in instructions | Add explicit UTC-to-local conversion instruction |
| Chat preview is unpredictable | Expected behavior -- LLM non-determinism | Use voice preview for reliable testing |
| Agent doesn't greet caller | Welcome Message field is empty | Set Welcome Message (separate from Instructions) |
| Agent doesn't appear in CCAI Config dropdown | Agent not deployed | Click Deploy in AI Agent Studio first |
| Flow Outcomes data doesn't reach agent | Notify AI Agent toggle OFF in Connect flow | Enable in Flow Settings > Flow Outcomes > Last Execution Status |

---

## Key Sources

- [Webex AI Agent Studio Administration Guide](https://help.webex.com/en-us/article/ncs9r37/Webex-AI-Agent-Studio-Administration-guide)
- [Configure custom data and custom events for AI agents](https://help.webex.com/en-us/article/n5uo60x/Configure-custom-data-and-custom-events-for-AI-agents)
- [Guidelines and best practices](https://help.webex.com/en-us/article/nelkmxk/Guidelines-and-best-practices-for-automating-with-AI-agent)
- [Use AI agents for customer interactions](https://help.webex.com/en-us/article/s0qro1/Use-AI-agents-for-customer-interactions)
