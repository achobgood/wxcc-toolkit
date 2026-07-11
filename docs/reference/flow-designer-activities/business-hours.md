## Business Hours Activity

Checks whether the current time falls within a configured Business Hours schedule and routes the call accordingly.

You can configure an error-handling path (Undefined Error) to handle system errors that may occur during flow execution.

If any of the ordered list inputs is empty, Flow Designer throws a flow validation error. You must resolve these errors before publishing the flow.

### Configuration

| Field | Description |
|---|---|
| Activity Label | Name for the activity |
| Activity Description | Optional description |
| Schedule Details | Select either **Static Business Hours** (pick a schedule from the dropdown) or **Variable Business Hours** (select a flow variable for dynamic schedule selection — see Dynamic Variables in Activities) |

When using a variable for dynamic selection, the variable must resolve to a valid Business Hours entity ID at runtime. If it doesn't match, the flow moves to the error path.

### Creating Business Hours Schedules

Business Hours schedules are created in **Control Hub > Contact Center > Business Hours**:

1. Navigate to **Control Hub > Contact Center > Business Hours**
2. Click **Create Business Hours**
3. Configure working hours (shifts) per day of the week
4. Add holiday dates (specific dates when the contact center is closed)
5. Add overrides (temporary schedule changes that take precedence over normal hours)
6. Save — the schedule becomes available in Flow Designer's Business Hours activity dropdown

### Output Paths

| Output Path | Fires When | Precedence |
|---|---|---|
| **Overrides** | Current time matches an override in the schedule | Highest — overrides take precedence over both working hours and holidays |
| **Holidays** | Current date matches a configured holiday | Takes precedence over working hours |
| **Working Hours** | Current time falls within the configured shift timing | Primary path for normal operations |
| **Default** | None of the above evaluated to true | Fallback |

### Output Variables

| Variable | Description |
|---|---|
| `BusinessHours.WorkingHoursShift_name` | Name of the shift defined in the working hours schedule |
| `BusinessHours.Holidays_Name` | Name of the holiday if the current day is a holiday |
| `BusinessHours.Overrides_Name` | Name of the override matching the current time |
| `BusinessHours.Status` | Which output path was chosen (working hours, holidays, override, or default) |

### Failure Codes

The Business Hours activity does not expose enumerated failure codes. There are no `FailureCode` or `FailureDescription` output variables.

The only error path is **Undefined Error**, which fires on system errors during flow execution (e.g., the variable for dynamic schedule selection does not resolve to a valid Business Hours entity ID at runtime).

> **Documentation pending** — Cisco help docs do not enumerate specific failure codes for the Business Hours activity. If Cisco adds failure codes in a future release, this section should be updated.

### Restrictions

- **Validation error on empty inputs:** If any of the ordered list inputs is empty, Flow Designer throws a flow validation error. You must resolve these errors before publishing the flow.
- **Variable schedule resolution:** When using a variable for dynamic schedule selection, the variable must resolve to a valid Business Hours entity ID at runtime. If it does not match, the flow moves to the Undefined Error path.
- **Self-loop limit:** Business Hours does not appear in the Cisco-documented self-loop limits table. It is not listed alongside activities like Callback (10), Queue Contact (100), or Menu (100).

> **Documentation pending** — event flow eligibility for Business Hours is not verified against Cisco help docs. The Cisco documentation does not explicitly state whether this activity can or cannot be used in event flows.

### Common Patterns

```
NewContact → Business Hours
  ├── Overrides → [special handling per override name]
  ├── Working Hours → Virtual Agent V2 / Queue Contact
  ├── Holidays → Play Message ("We are closed for the holiday") → Disconnect
  └── Default → Play Message ("Our hours are...") → Disconnect / Voicemail
```

---

