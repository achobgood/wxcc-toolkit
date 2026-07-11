# WxCC Provisioning API — Programmatic Resource Creation

<!-- ref-tag: wxcc-provisioning-v1 -->

The WxCC Provisioning API creates Contact Center resources (teams, queues, business hours, entry points) that the Flow Store API cannot. Use these patterns when building flows programmatically — the flow needs queues and business hours to exist before it can reference them.

**Base URL:** `https://api.wxcc-us1.cisco.com` (US1 region)
**Auth:** `Authorization: Bearer <token>` (same Webex token used for Flow Store)

## Discover Existing Resources

Before creating new resources, check what exists. Use `wxcli` or direct API calls:

```bash
wxcli cc-site list          # Sites
wxcli cc-team list          # Teams
wxcli cc-queue list         # Queues
wxcli cc-business-hour list # Business Hours
wxcli cc-entry-point list   # Entry Points
wxcli cc-global-vars list   # Global Variables (use -o json for UUIDs)
```

## Create a Team

```bash
curl -s -X POST "https://api.wxcc-us1.cisco.com/organization/{orgId}/team" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MyTeam",
    "siteId": "<site-uuid>",
    "teamType": "AGENT",
    "teamStatus": "IN_SERVICE",
    "active": true
  }'
```

| Field | Required | Notes |
|-------|----------|-------|
| `name` | Yes | Team name |
| `siteId` | Yes | UUID of the site (from `wxcli cc-site list`) |
| `teamType` | Yes | `AGENT` or `CAPACITY` |
| `teamStatus` | Yes | `IN_SERVICE` — omitting causes 409 error |
| `active` | Yes | `true` or `false` — omitting causes 400 error |

## Create a Queue

Queues require many fields that are not obvious from the API docs. Copy the structure below and customize.

```bash
curl -s -X POST "https://api.wxcc-us1.cisco.com/organization/{orgId}/contact-service-queue" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MyQueue",
    "queueType": "INBOUND",
    "channelType": "TELEPHONY",
    "routingType": "LONGEST_AVAILABLE_AGENT",
    "queueRoutingType": "TEAM_BASED",
    "serviceLevelThreshold": 60,
    "maxTimeInQueue": 3600,
    "maxActiveContacts": 0,
    "checkAgentAvailability": false,
    "active": true,
    "parkingPermitted": false,
    "recordingPermitted": false,
    "monitoringPermitted": true,
    "recordingAllCallsPermitted": false,
    "pauseRecordingPermitted": true,
    "recordingPauseDuration": 10,
    "defaultMusicInQueueMediaFileId": "<music-file-uuid>",
    "callDistributionGroups": [
      {
        "agentGroups": [{"teamId": "<team-uuid>"}],
        "order": 1,
        "duration": 0
      }
    ]
  }'
```

| Field | Required | Notes |
|-------|----------|-------|
| `name` | Yes | Queue name |
| `queueType` | Yes | `INBOUND` or `OUTBOUND` |
| `channelType` | Yes | `TELEPHONY`, `EMAIL`, `CHAT`, `SOCIAL_CHANNEL`, etc. |
| `routingType` | Yes | `LONGEST_AVAILABLE_AGENT`, `SKILLS_BASED`, `CIRCULAR`, `LINEAR` |
| `queueRoutingType` | Yes | `TEAM_BASED`, `SKILL_BASED`, `AGENT_BASED` |
| `serviceLevelThreshold` | Yes | Seconds — SLA target for queue |
| `maxTimeInQueue` | Yes | Seconds — max wait before overflow |
| `maxActiveContacts` | Yes | `0` = unlimited |
| `checkAgentAvailability` | Yes | Boolean |
| `active` | Yes | Boolean |
| `parkingPermitted` | Yes | Boolean — 400 error if omitted |
| `recordingPermitted` | Yes | Boolean — 400 error if omitted |
| `monitoringPermitted` | Yes | Boolean — 400 error if omitted |
| `recordingAllCallsPermitted` | Yes | Boolean — 400 error if omitted |
| `pauseRecordingPermitted` | Yes | Boolean — 400 error if omitted |
| `recordingPauseDuration` | No | Integer seconds (default 10) |
| `defaultMusicInQueueMediaFileId` | Yes | UUID of hold music audio file — 400 error if omitted. Get from an existing queue. |
| `callDistributionGroups` | Yes | At least one CDG with at least one `teamId`. 400 error if omitted. |

**Getting the music file UUID:** Query an existing queue: `curl -s "https://api.wxcc-us1.cisco.com/organization/{orgId}/contact-service-queue/{queueId}" -H "Authorization: Bearer $TOKEN"` and extract `defaultMusicInQueueMediaFileId`.

## Create Business Hours

```bash
curl -s -X POST "https://api.wxcc-us1.cisco.com/organization/{orgId}/business-hours" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MyBusinessHours",
    "description": "Mon-Fri 8AM-5PM Eastern",
    "timezone": "America/New_York",
    "workingHours": [
      {
        "name": "Weekday-Shift",
        "days": ["MON", "TUE", "WED", "THU", "FRI"],
        "startTime": "08:00",
        "endTime": "17:00"
      }
    ]
  }'
```

| Field | Required | Notes |
|-------|----------|-------|
| `name` | Yes | Schedule name. Pattern: `^[a-zA-Z0-9_-]+(\s?[a-zA-Z0-9_-]+)*$` (max 80 chars) |
| `timezone` | Yes | IANA timezone (e.g., `America/New_York`, `America/Chicago`) |
| `workingHours` | Yes | Array of shift objects |
| `workingHours[].name` | Yes | Shift name. Same pattern as parent name — no special characters. Use hyphens, not spaces with special chars. |
| `workingHours[].days` | Yes | **Array** of 3-letter uppercase day codes: `SUN`, `MON`, `TUE`, `WED`, `THU`, `FRI`, `SAT`. NOT comma-separated string. |
| `workingHours[].startTime` | Yes | `HH:MM` format (24-hour) |
| `workingHours[].endTime` | Yes | `HH:MM` format (24-hour) |
| `holidaysId` | No | UUID of a holiday list (create separately via `cc-holiday-list`) |

**Gotcha:** `days` MUST be an array of strings, not a single comma-separated string. `"days": "MON,TUE"` causes "Bad payload: Cannot deserialize".

## Create an Entry Point

```bash
curl -s -X POST "https://api.wxcc-us1.cisco.com/organization/{orgId}/entry-point" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MyEntryPoint",
    "entryPointType": "INBOUND",
    "channelType": "TELEPHONY",
    "serviceLevelThreshold": 60,
    "maximumActiveContacts": 0,
    "active": true,
    "timezone": "America/New_York",
    "flowId": "<flow-uuid>",
    "flowTagId": "Latest",
    "musicOnHoldId": "<music-file-uuid>",
    "callbackEnabled": false
  }'
```

| Field | Required | Notes |
|-------|----------|-------|
| `name` | Yes | Entry point name |
| `entryPointType` | Yes | `INBOUND` — 400 error if omitted ("invalid value") |
| `channelType` | Yes | `TELEPHONY`, `EMAIL`, `CHAT`, `SOCIAL_CHANNEL` |
| `serviceLevelThreshold` | Yes | Seconds |
| `maximumActiveContacts` | Yes | `0` = unlimited — 400 error if omitted |
| `active` | Yes | Boolean |
| `timezone` | No | IANA timezone |
| `flowId` | No | UUID of the Flow Designer flow to assign |
| `flowTagId` | No | `Latest`, `Dev`, `Test`, or `Live` |
| `musicOnHoldId` | No | UUID of hold music audio file |
| `callbackEnabled` | No | Boolean |

**Gotcha:** `flowId` assignment may fail with 500 error on some orgs. If it does, create the EP without `flowId`, then update it separately via PUT.

## wxcli Bug: Body Sent as Query Parameter

The auto-generated `wxcli cc-team create --team-dto '{...}'` and similar commands send the JSON payload as a URL-encoded query parameter instead of the request body. This causes 400 errors because the API receives an empty body.

**Workaround:** Use direct `curl` calls instead of `wxcli` for CC resource creation. The `wxcli cc-* list` and `wxcli cc-* show` commands (GET requests) work correctly.

## Provisioning Pipeline for Flow Building

When building a flow programmatically, provision resources in this order:

```
1. wxcli cc-site list         → confirm site exists (usually pre-provisioned)
2. Create team(s)             → curl POST /organization/{org}/team
3. Create queue(s)            → curl POST /organization/{org}/contact-service-queue
4. Create business hours      → curl POST /organization/{org}/business-hours
5. wxcc-flow global-vars      → get global variable UUIDs for FlowIR
6. Compose FlowIR             → reference queue/BH UUIDs + global var metadata
7. wxcc-flow validate         → dry-run check
8. wxcc-flow create           → import flow
9. wxcc-flow publish          → publish draft
10. Create entry point        → curl POST /organization/{org}/entry-point (with flowId)
11. Assign PSTN number        → Control Hub or wxcli numbers (Webex Calling API)
```
