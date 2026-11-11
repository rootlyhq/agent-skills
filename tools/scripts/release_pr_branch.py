#!/usr/bin/env python3
"""Select the single prepared release branch, allowing release-please's no-change output."""

import json
import os
import re
from pathlib import Path


def select(created, payload):
    if created != "true":
        return ""
    prs = json.loads(payload)
    if not isinstance(prs, list) or len(prs) != 1 or not isinstance(prs[0], dict):
        raise ValueError("Expected one prepared release PR")
    branch = prs[0].get("headBranchName")
    if not isinstance(branch, str) or not re.fullmatch(r"release-please--[A-Za-z0-9._/-]+", branch):
        raise ValueError("Missing or invalid release branch")
    return branch


if __name__ == "__main__":
    branch = select(os.environ.get("PRS_CREATED", ""), os.environ.get("RELEASE_PRS", ""))
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        output.write(f"branch={branch}\n")
