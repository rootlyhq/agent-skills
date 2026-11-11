"""Explicit coverage/provenance contract for a release fidelity matrix."""

import hashlib
import json

import fidelity_contract
import fidelity_judge

ARMS = ("claude-fable", "claude-opus", "claude-sonnet", "codex-default")
# Any case with format expectations can be run and graded; release clearance
# requires exactly the five cases the release matrix is defined over.
CASES = tuple(json.loads(fidelity_contract.EXPECTATIONS.read_text()))
RELEASE_CASES = ("deploy-shared-upgrade", "deploy-no-shared-upgrade",
                 "urgent-human-mitigation", "urgent-execution-not-started",
                 "urgent-execution-started")


def manifest(package, arms=ARMS, cases=RELEASE_CASES, repetitions=3):
    if (not arms or len(set(arms)) != len(arms) or not set(arms) <= set(ARMS)
            or not cases or len(set(cases)) != len(cases) or not set(cases) <= set(CASES)
            or type(repetitions) is not int or not 1 <= repetitions <= 10):
        raise ValueError("Invalid matrix arms, cases or repetition count")
    return {"version": 1, "arms": list(arms), "cases": list(cases), "repetitions": repetitions,
            "package_inventory_sha256": fidelity_judge.file_sha(package / "release-inventory.json"),
            "evidence_sha256": {case: hashlib.sha256(fidelity_judge.scenario_evidence(case).encode()).hexdigest()
                                for case in cases}}


def validate(matrix, package):
    """Fail before model calls on absent, partial, duplicated or mixed results."""
    errors, folders = [], []
    try:
        data = json.loads((matrix / "matrix-manifest.json").read_text())
        expected = manifest(package, data["arms"], data["cases"], data["repetitions"])
        if data != expected:
            errors.append("matrix_manifest_or_evidence_changed")
        if (set(data["arms"]) != set(ARMS) or set(data["cases"]) != set(RELEASE_CASES)
                or data["repetitions"] < 3):
            errors.append("release_requires_all_arms_cases_and_three_repetitions")
        inventory = json.loads((package / "release-inventory.json").read_text())
        if not isinstance(inventory, dict) or not inventory:
            raise ValueError("Empty package inventory")
        for name, digest in inventory.items():
            path = package / name
            if (not path.resolve().is_relative_to(package.resolve()) or path.is_symlink()
                    or fidelity_judge.file_sha(path) != digest):
                errors.append("package_content_changed")
                break
        desired = {}
        for arm in data["arms"]:
            client, model = arm.split("-", 1)
            for case in data["cases"]:
                for repeat in range(1, data["repetitions"] + 1):
                    name = f"{arm}/{client}-{case}-run-{repeat:02d}/result.json"
                    desired[name] = (client, model, case, repeat)
        found = {p.relative_to(matrix).as_posix(): p for p in matrix.rglob("result.json")}
        if set(found) != set(desired):
            errors.append("matrix_missing_or_unexpected_results")
        for name in sorted(set(found) & set(desired)):
            if found[name].is_symlink() or not found[name].resolve().is_relative_to(matrix.resolve()):
                errors.append("unsafe_result_path:" + name)
                continue
            result = json.loads(found[name].read_text())
            if not isinstance(result, dict):
                raise ValueError("Invalid result object")
            client, model, case, repeat = desired[name]
            if (result.get("client"), result.get("case"), result.get("repeat")) != (client, case, repeat):
                errors.append("result_identity_mismatch:" + name)
            if result.get("requested_model") != (model if client == "claude" else None):
                errors.append("requested_model_mismatch:" + name)
            if result.get("package_inventory_sha256") != expected["package_inventory_sha256"]:
                errors.append("result_package_mismatch:" + name)
            if not result.get("model") and result.get("status") == "completed":
                errors.append("missing_model_identity:" + name)
            folders.append(found[name].parent)
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append("invalid_matrix:" + type(error).__name__)
    if not folders:
        errors.append("empty_matrix")
    return folders, errors
