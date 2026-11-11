#!/usr/bin/env python3
"""Retain native strict-validation evidence for a clean Claude package; no model/MCP."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def validation_summary(stdout):
    """Fail closed on absent/changed diagnostics, not just a zero process exit."""
    try:
        data = json.loads(stdout)
        manifest = data["manifest"]
        target, kind = data["target"], manifest["type"]
        if (not isinstance(target, str) or manifest["file"] != target
                or kind not in ("plugin", "marketplace") or not isinstance(data["contents"], list)):
            raise ValueError("Unexpected validation target or result shape")
        counts = {"errors": 0, "warnings": 0}

        def count(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in counts:
                        if not isinstance(item, list):
                            raise ValueError("Diagnostics must be arrays")
                        counts[key] += len(item)
                    else:
                        count(item)
            elif isinstance(value, list):
                for item in value:
                    count(item)

        # Require explicit manifest diagnostics, then include nested contents.
        if not isinstance(manifest["errors"], list) or not isinstance(manifest["warnings"], list):
            raise ValueError("Missing manifest diagnostics")
        count(data)
        return {"target": target, "type": kind, "error_count": counts["errors"],
                "warning_count": counts["warnings"], "success": data.get("success"),
                "strict": data.get("strict"),
                "passed": data.get("success") is True and data.get("strict") is True and not any(counts.values())}
    except (ValueError, KeyError, TypeError) as error:
        return {"passed": False, "error": f"Invalid validation JSON: {error}"}


def check(package, output):
    output.mkdir(parents=True, exist_ok=False)
    report = {"package": str(package), "checks": [], "passed": False}
    try:
        report["inventory_sha256"] = hashlib.sha256((package / "release-inventory.json").read_bytes()).hexdigest()
        report["client_version"] = subprocess.check_output(["claude", "--version"], text=True, timeout=30).strip()
        for name, path in (("directory", package), ("plugin", package / ".claude-plugin/plugin.json"),
                           ("marketplace", package / ".claude-plugin/marketplace.json")):
            command = ["claude", "plugin", "validate", "--strict", "--json", str(path)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            (output / (name + ".stdout")).write_text(result.stdout)
            (output / (name + ".stderr")).write_text(result.stderr)
            validation = validation_summary(result.stdout)
            expected = {str(package / ".claude-plugin" / (kind + ".json")): kind
                        for kind in ("plugin", "marketplace")}
            target = validation.get("target")
            validation["target_matches"] = (target in expected and expected[target] == validation.get("type")
                                            and (name == "directory" or target == str(path)))
            report["checks"].append({"name": name, "command": command, "exit_code": result.returncode,
                                     "validation": validation})
        report["passed"] = all(item["exit_code"] == 0 and item["validation"]["passed"]
                               and item["validation"]["target_matches"] for item in report["checks"])
        report["validated_targets"] = sorted({item["validation"]["target"] for item in report["checks"]
                                             if item["exit_code"] == 0 and item["validation"]["passed"]
                                             and item["validation"]["target_matches"]})
    except (OSError, subprocess.SubprocessError) as error:
        report["error"] = type(error).__name__ + ": " + str(error)
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = check(args.package.resolve(), args.output.resolve())
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)
