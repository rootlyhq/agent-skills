#!/usr/bin/env python3
"""Experimental, local action-state gate. Not installed by the runtime package.

The host supplies an independently curated evidence snapshot; the model supplies
only a candidate. This is not a natural-language fact checker or access control.
Only the deterministic rendering of an accepted candidate may be displayed.
"""

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

STATES = {
    "approval": ("unknown", "proposed", "approved", "declined"),
    "execution": ("unknown", "not_started", "in_progress", "completed"),
}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}\Z")
MAX_BYTES = 262144


class Invalid(ValueError):
    """An input failed closed. Messages never echo untrusted input values."""


def parse_json(raw):
    if len(raw.encode("utf-8")) > MAX_BYTES:
        raise Invalid("input_too_large")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Invalid("duplicate_json_key")
            result[key] = value
        return result

    def constant(_):
        raise Invalid("nonfinite_json_number")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except Invalid:
        raise
    except (ValueError, RecursionError) as error:
        raise Invalid("invalid_json") from error


def exact_keys(value, keys, where):
    if type(value) is not dict or set(value) != set(keys):
        raise Invalid(where + ":invalid_fields")


def identifier(value, where):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise Invalid(where + ":invalid_identifier")


def validate_evidence(evidence):
    exact_keys(evidence, ("version", "snapshot_id", "action_id", "label", "as_of", "facts"), "evidence")
    if type(evidence["version"]) is not int or evidence["version"] != 1:
        raise Invalid("evidence:unsupported_version")
    for key in ("snapshot_id", "action_id"):
        identifier(evidence[key], "evidence:" + key)
    label = evidence["label"]
    if (not isinstance(label, str) or not 1 <= len(label) <= 160 or not label.strip()
            or any(unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in label)):
        raise Invalid("evidence:invalid_label")
    stamp = evidence["as_of"]
    if not isinstance(stamp, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", stamp):
        raise Invalid("evidence:invalid_as_of")
    try:
        datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise Invalid("evidence:invalid_as_of") from error
    facts = evidence["facts"]
    if type(facts) is not list or len(facts) > 128:
        raise Invalid("evidence:invalid_facts")
    seen = set()
    for fact in facts:
        exact_keys(fact, ("id", "action_id", "source_id", "field", "value", "eligibility"), "fact")
        for key in ("id", "action_id", "source_id"):
            identifier(fact[key], "fact:" + key)
        if fact["id"] in seen:
            raise Invalid("evidence:duplicate_fact_id")
        seen.add(fact["id"])
        field = fact["field"]
        if not isinstance(field, str) or field not in STATES or fact["value"] not in STATES[field][1:]:
            raise Invalid("fact:invalid_state")
        if fact["eligibility"] not in ("usable", "stale", "not_authorized"):
            raise Invalid("fact:invalid_eligibility")
    return evidence


def eligible(evidence, field):
    return [f for f in evidence["facts"] if f["field"] == field
            and f["eligibility"] == "usable" and f["action_id"] == evidence["action_id"]]


def expected(evidence, field):
    facts = eligible(evidence, field)
    values = {f["value"] for f in facts}
    if len(values) == 1:
        return next(iter(values)), "reported"
    return "unknown", "conflicting_reports" if values else "no_usable_report"


def model_evidence(evidence):
    """Do not send excluded or other-action records to a model in the first place."""
    validate_evidence(evidence)
    return {**evidence, "facts": eligible(evidence, "approval") + eligible(evidence, "execution")}


def candidate_schema():
    properties = {"snapshot_id": {"type": "string"}, "action_id": {"type": "string"}}
    for field, states in STATES.items():
        properties[field] = {
            "type": "object", "additionalProperties": False,
            "properties": {"state": {"type": "string", "enum": list(states)},
                           "evidence_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["state", "evidence_ids"],
        }
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties)}


def check(evidence, candidate):
    """Validate shape, binding, evidence eligibility and state entailment.

    A schema-valid output is still rejected if approval was used as evidence of
    execution/nonexecution. Unknown needs no citations; known states need at
    least one usable, same-field, same-action citation. Conflicting usable reports
    force unknown, regardless of which subset the model chooses to cite.
    """
    validate_evidence(evidence)
    exact_keys(candidate, candidate_schema()["required"], "candidate")
    for key in ("snapshot_id", "action_id"):
        if candidate[key] != evidence[key]:
            raise Invalid("candidate:" + key + ":mismatch")
    for field, states in STATES.items():
        claim = candidate[field]
        exact_keys(claim, ("state", "evidence_ids"), field)
        if claim["state"] not in states:
            raise Invalid(field + ":invalid_state")
        ids = claim["evidence_ids"]
        if type(ids) is not list or len(ids) > 128:
            raise Invalid(field + ":invalid_evidence_ids")
        for value in ids:
            identifier(value, field + ":evidence_id")
        if len(ids) != len(set(ids)):
            raise Invalid(field + ":duplicate_citation")
        state, _ = expected(evidence, field)
        if claim["state"] != state:
            raise Invalid(field + ":unsupported_state")
        if state == "unknown":
            if ids:
                raise Invalid(field + ":unknown_requires_empty_citations")
        else:
            allowed = {f["id"] for f in eligible(evidence, field) if f["value"] == state}
            if not ids or not set(ids) <= allowed:
                raise Invalid(field + ":unsupported_citation")


def evaluate(evidence, candidate):
    """Fail closed. No unvalidated candidate prose is returned, even on errors."""
    try:
        check(evidence, candidate)
    except Invalid as error:
        return {"accepted": False, "errors": [str(error)], "rendered": None}
    # Use only host values, never arbitrary text or citations from the candidate.
    label = re.sub(r"([\\`*_{}\[\]()<>#!|])", r"\\\1", evidence["label"])
    lines = ["Action-state excerpt — not an incident assessment", "",
             f"Action: {label}", f"Evidence snapshot: {evidence['snapshot_id']} (as of {evidence['as_of']})."]
    wording = {
        "approval": {"proposed": "Proposal reported", "approved": "Approval reported", "declined": "Approval declined, as reported"},
        "execution": {"not_started": "Not started, as explicitly reported", "in_progress": "Execution in progress, as reported", "completed": "Execution completed, as reported"},
    }
    for field in STATES:
        state, reason = expected(evidence, field)
        if state == "unknown":
            suffix = "conflicting usable reports" if reason == "conflicting_reports" else "no usable report in this snapshot"
            lines.append(f"{field.capitalize()} status unknown: {suffix}.")
        else:
            refs = ", ".join(f"{f['id']} / {f['source_id']}" for f in eligible(evidence, field))
            lines.append(f"{wording[field][state]} ({refs}).")
    lines += ["", "These are attributed reports, not independent verification of recovery or cause.",
              "This excerpt does not assess whether to act, authorize execution, or execute anything."]
    return {"accepted": True, "errors": [], "rendered": "\n".join(lines) + "\n"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True, help="Host-curated snapshot, not model-supplied evidence")
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence = parse_json(args.evidence.read_text())
        candidate = parse_json(args.candidate.read_text())
        result = evaluate(evidence, candidate)
        result.update(evidence_sha256=digest(evidence), candidate_sha256=digest(candidate))
    except (Invalid, OSError, UnicodeError) as error:
        result = {"accepted": False, "errors": [str(error) if isinstance(error, Invalid) else "input_read_failed"], "rendered": None}
    print(json.dumps(result, indent=2))
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
