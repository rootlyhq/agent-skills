# Authoring results

For a draft, show the proposed name, description and complete body. Include
`enabled: false` and any caller or owner settings the user selected. Identify
material missing inputs, the relevant existing match if one was found, and the
specific creation authorization still needed. A draft has not been saved.

For creation, report the actual returned ID or slug, the stored enabled state,
and which fields were verified by readback. Use a returned link only if supplied;
do not fabricate a dashboard URL. Explain a mismatch or failed verification.
Do not claim a successful create did not happen because its readback failed.

For an ambiguous write result, say creation is uncertain, what reconciliation
was attempted, and why another write was not made. A later matching skill may
be reported as present; attribute its creation to the timed-out call only when
evidence connects the two. Do not turn a timeout into
"not created" or issue a duplicate create automatically.

Creation is not activation, execution or proof of skill quality. Report actual
tool calls honestly. Do not say "nothing changed" after creating a skill, and
do not claim live tests or Git sync when only content was reviewed.
