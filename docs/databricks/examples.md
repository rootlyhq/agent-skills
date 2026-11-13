# Examples with Rootly and Databricks

These examples are starting points, not executed demonstrations. Use authorized
records and an explicitly selected connection. Report unavailable sources and
partial results rather than filling gaps with plausible details.

## Agent prompts

| Workflow | Example request | Evidence the answer should retain |
|---|---|---|
| Incident response | Summarize this incident's observed impact and recent changes; separate hypotheses and recommend the next checks. | Incident identifiers, source times and support for causal claims |
| Alert triage | Review these alerts and recommend whether they belong to an existing incident. | Matching evidence, uncertainty and missing impact information |
| Deploy check | Assess this proposed change against relevant incidents and service context. | Exact change, service mapping and limits of the available telemetry |
| Service health | Summarize this service's health for the supplied window. | Baselines, traffic coverage and missing signals |
| On-call | Check current coverage for this service and summarize any gaps. | Live shifts, timezone and confirmed service ownership |
| Communications | Draft an internal update using only the confirmed evidence. | Audience, observation window and unsupported details omitted |
| Retrospective | Organize this incident's evidence into a retrospective draft. | Timeline sources, disputed explanations and follow-up questions |

Install and load the corresponding canonical skill. Do not copy a separate
version of its instructions into an agent prompt or notebook. The agent may
recommend or draft; these examples do not authorize remote writes.

## Fictional triage walkthrough

Supply the following as explicit demo evidence, without calling a live service:

- A deployment began at 10:00 UTC.
- A supplied monitor reports request failures from 10:02 to 10:05 UTC.
- The record does not identify an active incident or confirm the deployment as a cause.

Ask the agent to separate observations, hypotheses and missing information, then
recommend the next checks under the applicable incident policy. A supported
answer can describe the time overlap. It cannot report a confirmed root cause,
invent an incident attachment or claim that anyone rolled back the deployment.

## Fictional mitigation walkthrough

Supply a record that says a rollback plan was validated and approved, but that
execution has not started. Ask for a stakeholder update. The draft should retain
the actual action state. Approval is not evidence of execution or recovery.

Change the evidence so execution has started but the result is unknown, then
check that the answer changes accordingly. Keep these demo records separate
from an actual production incident and label screenshots as fictional evidence.

## A bounded live walkthrough

With appropriate authorization, identify the connected Rootly organization,
select one permitted incident and retrieve only the details needed for a narrow
question. Inspect tool schemas and real returned IDs. State the observation
window, unavailable sources and whether the sample is partial.

Request a draft update and verify every factual assertion against the retrieved
evidence. Do not publish the draft, change the incident or page a responder.
Deployment metadata, job failures, logs and customer-impact metrics require
their own authorized sources; the MCP connection does not fabricate them.
