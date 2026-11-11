"""Explicit coverage/provenance contract for a release fidelity matrix."""

import hashlib
import json

import fidelity_contract
import fidelity_inputs
import fidelity_judge

ARMS = ("claude-fable", "claude-opus", "claude-sonnet", "codex-default")
# Any case with format expectations can be run and graded; release clearance
# requires exactly the five cases the release matrix is defined over.
CASES = tuple(json.loads(fidelity_contract.EXPECTATIONS.read_text()))
RELEASE_CASES = ("deploy-shared-upgrade", "deploy-no-shared-upgrade",
                 "urgent-human-mitigation", "urgent-execution-not-started",
                 "urgent-execution-started")


def manifest(package, arms=ARMS, cases=RELEASE_CASES, repetitions=3, codex_model_override=None):
    if (not arms or len(set(arms)) != len(arms) or not set(arms) <= set(ARMS)
            or not cases or len(set(cases)) != len(cases) or not set(cases) <= set(CASES)
            or type(repetitions) is not int or not 1 <= repetitions <= 10):
        raise ValueError("Invalid matrix arms, cases or repetition count")
    return {"version": 2, "arms": list(arms), "cases": list(cases), "repetitions": repetitions,
            "codex_model_override": codex_model_override,
            "input_sources_sha256": fidelity_inputs.source_hashes(),
            "package_inventory_sha256": fidelity_judge.file_sha(package / "release-inventory.json"),
            "evidence_sha256": {case: hashlib.sha256(fidelity_judge.scenario_evidence(case).encode()).hexdigest()
                                for case in cases}}


def validate(matrix, package):
    """Fail before model calls on absent, partial, duplicated or mixed results."""
    errors, folders = [], []
    try:
        data = json.loads((matrix / "matrix-manifest.json").read_text())
        expected = manifest(package, data["arms"], data["cases"], data["repetitions"], data.get("codex_model_override"))
        if data != expected:
            errors.append("matrix_manifest_or_evidence_changed")
        if (set(data["arms"]) != set(ARMS) or set(data["cases"]) != set(RELEASE_CASES)
                or data["repetitions"] < 3):
            errors.append("release_requires_all_arms_cases_and_three_repetitions")
        inventory = json.loads((package / "release-inventory.json").read_text())
        if not isinstance(inventory, dict) or not inventory:
            raise ValueError("Empty package inventory")
        paths = list(package.rglob("*"))
        if (package.is_symlink() or any(p.is_symlink() or not (p.is_file() or p.is_dir()) for p in paths)
                or {p.relative_to(package).as_posix() for p in paths if p.is_file()}
                != set(inventory) | {"release-inventory.json"}):
            errors.append("package_membership_changed")
        for name, digest in inventory.items():
            path = package / name
            if (not isinstance(name, str) or path.relative_to(package).as_posix() != name
                    or not path.resolve().is_relative_to(package.resolve()) or path.is_symlink()
                    or not path.is_file() or fidelity_judge.file_sha(path) != digest):
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
            folder = found[name].parent
            hashes, sent = fidelity_inputs.expected_prompt(case, client)
            prompt = folder / "prompt.txt"
            if (prompt.is_symlink() or not prompt.is_file() or prompt.read_bytes() != sent.encode()
                    or any(result.get(key) != value for key, value in hashes.items())):
                errors.append("result_prompt_or_fixture_mismatch:" + name)
            override = data.get("codex_model_override") if client == "codex" else None
            if (result.get("codex_model_override") != override
                    or (override and result.get("status") == "completed" and result.get("model") != override)):
                errors.append("codex_model_override_mismatch:" + name)
            folders.append(folder)
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append("invalid_matrix:" + type(error).__name__)
    if not folders:
        errors.append("empty_matrix")
    return folders, errors
