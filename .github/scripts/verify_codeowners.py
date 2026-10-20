"""Validate this repository's declared maintainer at one immutable GitHub commit."""

import argparse
import base64
import json
import re
import subprocess
from collections.abc import Callable
from typing import Any

REPOSITORY = "loganpendragonmultiverse/digital-comic-duplicate-detector"
OWNER = "LoganPendragonmulti"
OWNER_ID = 6430701
EXPECTED = b"* @LoganPendragonmulti\n"


def verify(ref: str, fetch: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", ref) is None:
        raise ValueError("Ownership validation requires an exact 40-character commit SHA")
    owner = fetch("users/" + OWNER)
    if (
        owner["type"] != "User"
        or owner["id"] != OWNER_ID
        or owner["login"].casefold() != OWNER.casefold()
    ):
        raise ValueError("CODEOWNERS maintainer must resolve to the expected GitHub user")
    permission = fetch("repos/" + REPOSITORY + "/collaborators/" + OWNER + "/permission")
    if (
        permission["permission"] not in {"admin", "maintain", "write"}
        or permission["user"]["id"] != OWNER_ID
    ):
        raise ValueError("CODEOWNERS maintainer must have repository write access")
    contents = fetch("repos/" + REPOSITORY + "/contents/.github/CODEOWNERS?ref=" + ref)
    if contents["encoding"] != "base64":
        raise ValueError("GitHub must return base64 CODEOWNERS content")
    payload = base64.b64decode("".join(contents["content"].splitlines()), validate=True)
    if payload != EXPECTED:
        raise ValueError("Exact commit must declare the verified catch-all maintainer")
    errors = fetch("repos/" + REPOSITORY + "/codeowners/errors?ref=" + ref)
    if errors["errors"] != []:
        raise ValueError("GitHub reports CODEOWNERS errors at the exact commit")
    return {
        "passed": True,
        "commit": ref,
        "owner": OWNER,
        "owner_id": OWNER_ID,
        "permission": permission["permission"],
        "codeowners_errors": [],
        "content_verified": True,
    }


def github(path: str) -> dict[str, Any]:
    result = subprocess.run(["gh", "api", path], check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise TypeError("GitHub API response must be an object")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.ref, github), sort_keys=True))
    except (ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        raise SystemExit("Ownership validation failed: " + str(exc)) from exc


if __name__ == "__main__":
    main()
