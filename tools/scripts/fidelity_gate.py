#!/usr/bin/env python3
"""Release gate for evidence fidelity over native run results.

A run passes only when it completed, loaded the shared rules, satisfies the
deterministic output contract (scripts/fidelity_contract.py), and the judge
(scripts/fidelity_judge.py) finds no unlabeled inference. Any vote error fails
the gate and is never counted as a pass. With an odd vote count a majority
always decides over valid pass/fail votes, so a 2-1 pass is possible: every
judged row records its vote split and the quotes any vote flagged.
"""

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import fidelity_contract
import fidelity_judge
import fidelity_matrix


def grade_run(folder, votes, judge_model):
    result = json.loads((folder / "result.json").read_text())
    row = {"run": folder.name, "client": result["client"], "case": result["case"],
           "model": result.get("model"), "requested_model": result.get("requested_model"),
           "status": result["status"], "common_loaded": result.get("common_loaded")}
    reasons = []
    if result["status"] != "completed":
        reasons.append("run_not_completed:" + str(result.get("error", ""))[:120])
        row.update(gate="fail", reasons=reasons)
        return row
    if not result.get("common_loaded"):
        reasons.append("common_rules_not_loaded")
    if result.get("mechanics", {}).get("passed") is False:
        reasons.append("fixture_mechanics_failed")
    answer = (folder / "final.md").read_text()
    evidence = fidelity_judge.scenario_evidence(result["case"])
    expected = fidelity_contract.contract_expectations(result["case"])
    # Scenario expectations name the contract; a case can also declare the format
    # its question routes to. Investigation briefs have no table to parse.
    kind = (expected or {}).get("contract") or fidelity_contract.declared_format(result["case"])
    if kind in fidelity_contract.CONTRACTS:
        row["contract_violations"] = fidelity_contract.check(answer, kind, evidence, expected)
        reasons += ["contract:" + v for v in row["contract_violations"]]
    else:
        row["contract_violations"] = None
    # Positive controls: the judge only detects over-claiming, so a scenario whose
    # evidence resolves the question also has must-report findings.
    row["resolved_violations"] = fidelity_contract.check_resolved(answer, result["case"])
    reasons += ["resolved:" + v for v in row["resolved_violations"]]
    # Format applies to the final answer; fidelity applies to *all* visible prose.
    visible = (folder / "visible.md").read_text()
    if answer.strip() not in visible:
        reasons.append("final_missing_from_visible_text")
    verdict = fidelity_judge.judge(visible, result["case"], judge_model, votes,
                                   expected_model=fidelity_judge.calibrated_model())
    with (folder / "fidelity-judge.json").open("x") as output:
        output.write(json.dumps(verdict, indent=2) + "\n")
    row["judge"] = verdict["verdict"]
    # A 2-1 majority is weaker evidence than a unanimous one; keep the split.
    row["judge_votes"] = fidelity_judge.vote_split([v["verdict"] for v in verdict["votes"]])
    # Quotes flagged by at least one vote, not claims every vote rejected.
    row["judge_quotes_flagged_by_any_vote"] = sorted(
        {c["quote"] for v in verdict["votes"] for c in v.get("failing", [])})
    if verdict["verdict"] != "pass":
        reasons.append("judge:" + verdict["verdict"])
    row["format"] = fidelity_contract.detected_format(answer)
    row["format_expected"] = fidelity_contract.declared_format(result["case"])
    if row["format_expected"] and row["format"] != row["format_expected"]:
        reasons.append(f"format_routing:{row['format']}")
    row.update(gate="pass" if not reasons else "fail", reasons=reasons)
    return row

def grading_fingerprints():
    return {**fidelity_judge.calibration_fingerprints(),
            "agreement_sha256": fidelity_judge.file_sha(fidelity_judge.FIDELITY / "judge-agreement.json")}


def grade_round(folder, votes, judge_model, jobs):
    """Grade an exploratory scenario round over whatever runs the runner produced.

    This is not release clearance: there is no matrix coverage contract, and the
    deploy/focused format checker does not apply to investigation briefs. It
    reports per-run gate rows plus the format each repeat chose, so a routing
    inconsistency is visible instead of silently averaged away.
    """
    if type(votes) is not int or votes < 3 or votes % 2 == 0 or jobs < 1:
        raise ValueError("Require positive jobs and an odd number of at least three votes")
    folders = sorted({path.parent for path in folder.rglob("result.json")})
    if not folders:
        raise ValueError(f"No run results under {folder}")
    if (folder / "round-gate.json").exists() or any((f / "fidelity-judge.json").exists() for f in folders):
        raise FileExistsError("Refusing to overwrite retained grades; use a new output directory/copy")
    fingerprints = grading_fingerprints()
    errors = fidelity_judge.calibration_errors(model=judge_model)
    rows = []
    if not errors:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            rows = list(pool.map(lambda f: grade_run(f, votes, judge_model), folders))
    if grading_fingerprints() != fingerprints:
        errors.append("grading_inputs_changed_during_run")
    formats = defaultdict(set)
    cells = defaultdict(lambda: {"pass": 0, "runs": 0})
    for row in rows:
        formats[row["case"]].add(row.get("format"))
        cells[row["case"]]["runs"] += 1
        cells[row["case"]]["pass"] += row["gate"] == "pass"
    inconsistent = sorted(case for case, seen in formats.items() if len(seen) > 1)
    summary = {
        "release_clearance": False, "judge_model": judge_model, "votes": votes,
        **fingerprints,
        "cases": {case: dict(cell) for case, cell in sorted(cells.items())},
        "formats": {case: sorted(seen) for case, seen in sorted(formats.items())},
        "format_inconsistent_cases": inconsistent,
        "runs": rows, "errors": errors,
        "passed": bool(rows) and not errors and not inconsistent
        and all(r["gate"] == "pass" for r in rows),
    }
    (folder / "round-gate.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def grade(matrix, votes, judge_model, jobs, package):
    if type(votes) is not int or votes < 3 or votes % 2 == 0 or jobs < 1:
        raise ValueError("Require positive jobs and an odd number of at least three votes")
    fingerprints = grading_fingerprints()
    folders, errors = fidelity_matrix.validate(matrix, package)
    errors += fidelity_judge.calibration_errors(model=judge_model)
    if (matrix / "gate.json").exists() or any((f / "fidelity-judge.json").exists() for f in folders):
        raise FileExistsError("Refusing to overwrite retained grades; use a new matrix/copy")
    rows = []
    if not errors:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            rows = list(pool.map(lambda f: grade_run(f, votes, judge_model), folders))
    if grading_fingerprints() != fingerprints:
        errors.append("grading_inputs_changed_during_run")
    _, final_errors = fidelity_matrix.validate(matrix, package)
    errors.extend(error for error in final_errors if error not in errors)
    table = defaultdict(lambda: defaultdict(lambda: {"pass": 0, "runs": 0}))
    for row in rows:
        arm = f"{row['client']}:{row['model'] or row['requested_model']}"
        cell = table[arm][row["case"]]
        cell["runs"] += 1
        cell["pass"] += row["gate"] == "pass"
    summary = {
        "judge_model": judge_model, "votes": votes,
        **fingerprints,
        "table": {arm: dict(cases) for arm, cases in table.items()},
        "runs": rows,
        "errors": errors,
        "passed": bool(rows) and not errors and all(r["gate"] == "pass" for r in rows),
    }
    (matrix / "gate.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def render(summary):
    cases = sorted({case for arm in summary["table"].values() for case in arm})
    lines = ["| Arm | " + " | ".join(cases) + " | Total |", "|---" * (len(cases) + 2) + "|"]
    for arm, cells in sorted(summary["table"].items()):
        passed = sum(c["pass"] for c in cells.values())
        runs = sum(c["runs"] for c in cells.values())
        lines.append(f"| {arm} | " + " | ".join(
            f"{cells[c]['pass']}/{cells[c]['runs']}" if c in cells else "-" for c in cases) + f" | {passed}/{runs} |")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix", type=Path)
    parser.add_argument("--package", type=Path, help="Exact exported package under test")
    parser.add_argument("--round", action="store_true",
                        help="Grade an exploratory scenario round instead of a release matrix")
    parser.add_argument("--votes", type=int, default=3)
    parser.add_argument("--judge-model", default="fable")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if args.round == bool(args.package):
        parser.error("Use --package for a release matrix or --round for an exploratory round")
    if args.round:
        summary = grade_round(args.matrix.resolve(), args.votes, args.judge_model, args.jobs)
        print(json.dumps({"cases": summary["cases"], "formats": summary["formats"]}, indent=2))
    else:
        summary = grade(args.matrix.resolve(), args.votes, args.judge_model, args.jobs, args.package.resolve())
        print(render(summary))
    for error in summary["errors"]:
        print(error)
    for row in summary["runs"]:
        if row["gate"] != "pass":
            print(row["run"], row["reasons"])
    raise SystemExit(0 if summary["passed"] else 1)
