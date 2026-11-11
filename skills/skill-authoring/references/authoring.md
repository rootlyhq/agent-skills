# Writing a useful Rootly AI skill

Write for the task and the intended caller. Explain when the procedure applies,
what evidence it needs, how to interpret that evidence, what decisions remain
with a human, and what useful result to return. Prefer one coherent workflow over
a collection of unrelated jobs. Check a neighboring skill before duplicating it.

Use the team's actual procedure and authorized references. Label proposed defaults
as proposals; do not invent project names, service mappings, thresholds, roles or
monitoring coverage. Include only organization details that change the procedure.
Keep private procedures in the intended Rootly organization, not this public repo.

Use a short name and a description that names the task and a useful trigger.
Keep the body readable Markdown. Include only the necessary prerequisites,
evidence interpretation, procedure, result expectations and absence paths.
The skill body must be usable where it will run: do not refer to local files,
other plugins or external connections unless that runtime can actually reach
them. Native Rootly skills are stored bodies; a local reference folder is not
automatically uploaded or synced. Resolve required authorized reference content
into the reviewed body, or make the missing dependency explicit.

Name capabilities in ordinary language and verified tool names where necessary.
Inspect actual schemas instead of embedding client-specific invocation syntax.
Do not use encodings, concealed instructions, secrets, claims of higher authority,
or instructions to ignore platform safeguards. State actions and permissions openly.
Read-only investigative instructions must not claim they grant write permission.

Before asking to create the skill, compare the draft with a concrete request it
should handle and one it should decline or route elsewhere. Note what cannot be
verified without a runtime test. A text review is not a completed model rehearsal.
When revising a draft, fix the observed failure while preserving useful behavior;
do not describe version history or user feedback as a measured usage assessment.
