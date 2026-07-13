---
name: configure-scripted-agent
description: |
  Configure a SCRIPTED AI agent in Webex AI Agent Studio. Walks through creating
  the agent, selecting the AI engine (Swiftmatch Pro, MindMeld), configuring
  intents with training phrases, defining entities and slot prompts, authoring
  responses with template keys, setting up context flow (entry/exit contexts),
  tuning AI engine settings, testing, and deployment.
  Use for: configuring a scripted AI agent in Agent Studio — intents, entities,
  responses, context flow, AI engine settings, deployment. Mid-pipeline skill —
  run design-scripted-agent first to produce the design doc, then this skill.
  NOT for: autonomous agents (use configure-ai-agent — autonomous agents use
  actions with LLM-driven descriptions, not intents/entities/responses),
  fulfillment wiring (use build-scripted-fulfillment — that builds the API call
  logic, this configures the agent itself), the full pipeline from scratch
  (use wxcc-agent-builder agent — it orchestrates everything).
allowed-tools: Read, Grep, Glob
argument-hint: [agent-name]
---

# Configure Scripted Agent Workflow

> **Autonomous agents?** This skill is for scripted agents. Autonomous agents use a different architecture (actions with LLM-driven descriptions instead of intents/entities/responses). Use `configure-ai-agent` for autonomous agents.

## Step 1: Load references

YOU MUST use the Read tool on each of these files. Do not proceed to Step 2 until all reads are complete.

1. Read `docs/reference/ai-agent-studio-scripted.md` for scripted agent Studio conventions
2. Read `docs/playbooks/scripted-agent-build.md` for the step-by-step build playbook
3. Read this skill's `reference.md` for the quick-reference cheat sheet

**Checkpoint — do NOT proceed until you can answer these from the docs you just read:**
- What AI engines are available for scripted agents, and which is recommended? (from `ai-agent-studio-scripted.md`)
- What is the correct CCAI Config dropdown value for a scripted agent? (from `ai-agent-studio-scripted.md`)
- How do you reference entity values in response templates? (from `scripted-agent-build.md`)

If you cannot answer all three, you skipped Step 1. Go back and read the docs.

## Step 2: Confirm prerequisites

Before configuring in AI Agent Studio, verify:

- A design document exists with intents, entities, responses, and context flow mapped out
- The user knows what API endpoints fulfillment will call (if any intents need fulfillment)
- The user has access to AI Agent Studio (Control Hub > Contact Center > AI Agents)

If no design document exists, tell the user to run `design-scripted-agent` first — this skill configures from a design, it does not create the design.

## Step 3: Create the Agent — `[AI Agent Studio]`

1. Open **AI Agent Studio**
2. Click **Create Agent** — or start from a **built-in template** if one matches the use case:
   - **Doctor's Appointment**: 4 intents (check availability, book, lookup, cancel) with slots pre-configured
   - **Track Package**: single intent with package number extraction
   - Templates include pre-authored utterances, entities, and responses — customize rather than build from scratch
3. Select **Scripted**
4. Enter **Agent Name** and **Description**
5. Select **AI Engine**:
   - **Swiftmatch Pro 2.0**: Recommended for most use cases (LLM-enhanced intent matching)
   - **Swiftmatch Pro 1.0**: Simpler, no LLM dependency
   - **MindMeld**: If you need entity roles (origin/destination patterns)
6. Click **Create**

## Step 4: Configure Profile Settings — `[AI Agent Studio → Profile]`

Navigate to the **Profile** section and set:

| Setting | Value |
|---------|-------|
| **Agent Goal** | One sentence purpose statement from the design doc |
| **Timezone** | Match the organization's timezone |
| **Custom Error Message** | "I'm experiencing technical difficulties. Please try again in a moment." |

## Step 5: Create Entities — `[AI Agent Studio → Scripts → Entities]`

**Important:** Create entities BEFORE intents, since you'll link entities to intents as slots.

For each entity from the design doc:

1. Click **Create Entity**
2. Enter **Name** (lowercase_underscores: `appointment_date`)
3. Select **Type** (cannot be changed after creation):
   - **Custom list**: Add all valid values with synonyms
   - **Regex**: Enter the pattern (e.g., `[A-Z]{3}\d{6}`)
   - **Digits**: Set the expected length
4. Configure type-specific settings
5. Click **Save**

Present entities as a table for the user to copy:

| Entity Name | Type | Configuration |
|-------------|------|---------------|
| (from design doc) | (from design doc) | (values/pattern/length) |

## Step 6: Create Intents — `[AI Agent Studio → Scripts → Intents]`

For each intent from the design doc:

### 6a. Basic Configuration
1. Click **Create Intent**
2. Enter **Intent Name** (e.g., `book_appointment`)
3. Enter **Description** (mandatory for Pro 2.0 — helps NLU distinguish similar intents)

### 6b. Add Utterances
1. Add training phrases — minimum 3 (10+ recommended for Pro 2.0)
2. Use **Generate variants** button to auto-generate additional phrases
3. **Annotate entities** in utterances: highlight entity values and tag them with the correct entity name

### 6c. Link Slots
1. Click **+Link** to connect an entity as a slot
2. Configure each slot:
   - **Required**: Toggle ON for mandatory data
   - **Retries**: Set retry count (2-3 recommended)
   - **Response**: Select which response template prompts for this slot
   - **Update slot values**: Toggle ON if the user should be able to change their answer

### 6d. Configure Contexts
1. **Entry Contexts**: Add context values required for this intent to match
2. **Exit Contexts**: Add context values this intent activates when matched, with **Duration** (number of turns the context stays active)

### 6e. Intent Settings
- **Reset slots after completion**: Toggle ON if slot values should clear after the intent completes
- **End conversation**: Toggle ON for terminal intents (e.g., goodbye)

Present each intent as a configuration block for the user:

```
Intent: [name]
Description: [from design doc]
Utterances: [list 10+ training phrases]
Slots: [entity_name (Required: yes/no, Retries: N)]
Entry Contexts: [list or "none"]
Exit Contexts: [context_name (Duration: N turns)]
```

## Step 7: Create Responses — `[AI Agent Studio → Scripts → Responses]`

### 7a. Intent Completion Responses
For each intent, create the response delivered after all slots are collected:

1. Click **Create Response**
2. Set the **Template Key** (e.g., `booking_confirmed`)
3. Select channel (Web is default)
4. Choose response type (Text, Quick Reply, List Message, etc.)
5. Write the response text, using variables:
   - `${entity.appointment_date}` — collected slot values
   - `${extra_params.customer_name}` — message parameters from the flow
   - `${eventStore.confirmation_number}` — data from custom events (voice)

### 7b. Slot Prompt Responses
For each required slot, create the prompt response:

1. Create a response with a descriptive template key (e.g., `ask_date`)
2. Write the prompt: "What date would you like your appointment?"
3. Link this response to the slot in the intent configuration (Step 6c)

### 7c. Channel-Specific Variants
For each response, add channel-specific formats:

1. Click the **channel selector dropdown**
2. Select a channel (WhatsApp, Voice, SMS, etc.)
3. Configure channel-appropriate response:
   - **WhatsApp**: Reply Button for yes/no, List Message for multiple options
   - **Voice**: Text (spoken by TTS) or Custom Event (for fulfillment handoff)
   - **Apple Messages**: List Picker, Time Picker, Form
   - **SMS**: Plain text (keep concise)

### 7d. Customize System Responses
Edit the built-in system responses:

| System Response | Customize To |
|----------------|-------------|
| **Welcome message** | Agent greeting from the design doc |
| **Fallback message** | "I didn't understand that. Could you rephrase?" |
| **Partial message** | "Did you mean one of these?" |
| **Agent handover** | "Let me connect you with a team member." |

## Step 8: Configure AI Engine Settings — `[AI Agent Studio → Profile → AI Engine]`

Navigate to **Profile > AI Engine** and tune:

| Setting | Recommendation |
|---------|---------------|
| **Fallback threshold** | Start at default; lower if fallback fires too often |
| **Partial match threshold** | Start at default; adjust based on testing |
| **Spellcheck in inference** | ON for text channels; helps with typos |
| **Expand contractions** | ON (handles "don't" → "do not") |
| **Prioritize slot filling** | ON if entity extraction is more important than intent switching |

## Step 9: Test the Agent — `[AI Agent Studio → Preview]`

### 9a. Chat Preview
1. Click **Preview** > **Chat**
2. Click **Start a Chat**
3. Test each intent with trained utterances AND novel phrasing
4. Verify correct intent classification
5. Verify slot prompts fire in order
6. Verify responses display correctly

### 9b. Voice Preview
1. Click **Preview** > **Voice**
2. Grant browser microphone access (use a headset)
3. Speak utterances naturally
4. Verify speech recognition handles entity formats

### 9c. Test Checklist
Present this checklist to the user:

| Test | Expected Result |
|------|----------------|
| Each intent matches with trained utterances | Correct intent classification |
| Each intent matches with novel phrasing | Correct intent (tests NLU generalization) |
| Required slots prompt correctly | Agent asks for each missing slot |
| Slot retries work | Agent re-asks after invalid input |
| Context chains work | Follow-up intents only available after prerequisite |
| Fallback fires on gibberish | Agent says fallback message |
| "Talk to an agent" triggers handover | Agent escalates |
| Per-channel responses render correctly | WhatsApp buttons, lists, etc. display |

## Step 10: Publish and Deploy — `[AI Agent Studio + Control Hub]`

### 10a. Publish
1. In AI Agent Studio, click **Publish**
2. Add a version description
3. The agent is now live and selectable in CCAI Configs

### 10b. Create CCAI Config
1. **Control Hub** > **Services** > **Contact Center** > **Tenant Settings** > **Integrations** > **Features**
2. Click **Create** new Contact Center AI Config
3. Select your published scripted agent
4. Name the config descriptively (e.g., `scripted-appointment-bot`)
5. Save

### 10c. Wire to Voice (Flow Designer)
1. Open your call flow in **WxCC Flow Designer**
2. Add a **Virtual Agent V2** activity
3. Select **"Webex AI Agent Scripted"** from the Contact Center AI Config dropdown
4. Select your published agent from the Virtual Agent dropdown
5. Wire output paths:
   - **Handled** → continue flow or end
   - **Escalated** → Queue Contact node
   - **Errored** → error handling
   - **Custom Event** → fulfillment logic (if applicable)

### 10d. Wire to Digital (Webex Connect)
1. Open your conversation flow in **Webex Connect**
2. In the **AI Agent** node:
   - Set Agent Type to **Scripted**
   - Select your agent
   - Configure Method: **Process Message**
3. Wire exit paths:
   - **onSuccess** → Channel Reply (with fulfillment branching if applicable)
   - **onAgentHandover** → Queue Task
   - **onError** → error handling

## Step 11: Present all config to user

Format everything for direct copy-paste into AI Agent Studio:

1. Agent Name and Description
2. AI Engine selection and rationale
3. Entity table (all entities with types and configuration)
4. Intent configurations (name, description, utterances, slots, contexts — one block per intent)
5. Response templates (template key, text, channel variants — one block per response)
6. System response customizations
7. AI Engine tuning settings
8. Test checklist
9. Deployment steps (Publish → CCAI Config → Wire to channel)

---

## CRITICAL REMINDERS

- **Entity type cannot be changed after creation.** If wrong, delete and recreate.
- **Pro 2.0 requires intent descriptions.** Without them, similar intents get confused.
- **Minimum 3 utterances per intent, 10+ recommended.** Use Generate variants for more.
- **Create entities BEFORE intents** — you need them to link as slots.
- **Template keys must match** between responses and fulfillment branching (Data Parser checks `$.model_state.template_key`).
- **Context duration is in turns, not time.** A duration of 3 means the context stays active for 3 conversational turns.
- **Scripted agents do NOT use action descriptions or `{{variable_name}}` syntax** — that is the autonomous pattern.

## ANTI-HALLUCINATION GUARD

Every field name, UI location, configuration detail, and syntax rule in your output MUST appear verbatim in the docs you loaded in Step 1. If you are about to write something you did not read in the docs:

1. STOP and say "I don't have that documented — would you like me to do a web search to find the correct answer?"
2. Wait for the user's response before proceeding.
3. If they approve, use the WebSearch tool to find the answer from official Cisco/Webex documentation.
4. Present what you found and mark it as `[FROM WEB SEARCH — not yet in project docs]` so the user knows it hasn't been verified against the local reference.
5. Do NOT mix web search results into your output without that label.

Do not invent plausible-sounding platform details under any circumstances.
