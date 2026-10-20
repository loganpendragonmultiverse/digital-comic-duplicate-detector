"""Exercise ownership identity, access, exact-ref and fail-closed API decisions."""

import base64
import copy
import unittest
from typing import Any

from verify_codeowners import EXPECTED, OWNER, OWNER_ID, REPOSITORY, verify

REF = "a" * 40


class OwnershipGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.responses: dict[str, dict[str, Any]] = {
            "users/" + OWNER: {"type": "User", "id": OWNER_ID, "login": OWNER},
            "repos/" + REPOSITORY + "/collaborators/" + OWNER + "/permission": {
                "permission": "admin",
                "user": {"id": OWNER_ID},
            },
            "repos/" + REPOSITORY + "/contents/.github/CODEOWNERS?ref=" + REF: {
                "encoding": "base64",
                "content": base64.b64encode(EXPECTED).decode(),
            },
            "repos/" + REPOSITORY + "/codeowners/errors?ref=" + REF: {"errors": []},
        }

    def fetch(self, path: str) -> dict[str, Any]:
        return copy.deepcopy(self.responses[path])

    def test_expected_user_and_exact_commit_pass(self) -> None:
        self.assertEqual(verify(REF, self.fetch)["owner_id"], OWNER_ID)

    def test_organization_and_changed_identity_fail(self) -> None:
        deltas: list[dict[str, Any]] = [
            {"type": "Organization"},
            {"id": 305315199},
            {"login": "another-user"},
        ]
        for delta in deltas:
            with self.subTest(delta=delta):
                saved = self.responses["users/" + OWNER].copy()
                self.responses["users/" + OWNER].update(delta)
                with self.assertRaises(ValueError):
                    verify(REF, self.fetch)
                self.responses["users/" + OWNER] = saved

    def test_readonly_and_missing_access_fail(self) -> None:
        path = "repos/" + REPOSITORY + "/collaborators/" + OWNER + "/permission"
        for permission in ["read", "triage", "none"]:
            with self.subTest(permission=permission):
                self.responses[path]["permission"] = permission
                with self.assertRaises(ValueError):
                    verify(REF, self.fetch)

    def test_permission_for_another_identity_fails(self) -> None:
        self.responses["repos/" + REPOSITORY + "/collaborators/" + OWNER + "/permission"]["user"][
            "id"
        ] = 1
        with self.assertRaises(ValueError):
            verify(REF, self.fetch)

    def test_old_organization_entry_fails(self) -> None:
        path = "repos/" + REPOSITORY + "/contents/.github/CODEOWNERS?ref=" + REF
        self.responses[path]["content"] = base64.b64encode(
            b"* @loganpendragonmultiverse\n"
        ).decode()
        with self.assertRaises(ValueError):
            verify(REF, self.fetch)

    def test_api_owner_errors_fail(self) -> None:
        self.responses["repos/" + REPOSITORY + "/codeowners/errors?ref=" + REF]["errors"] = [
            {"kind": "Unknown owner"}
        ]
        with self.assertRaises(ValueError):
            verify(REF, self.fetch)

    def test_missing_api_fields_fail(self) -> None:
        self.responses["repos/" + REPOSITORY + "/codeowners/errors?ref=" + REF] = {}
        with self.assertRaises(KeyError):
            verify(REF, self.fetch)

    def test_api_failure_is_not_a_pass(self) -> None:
        def fail(path: str) -> dict[str, Any]:
            raise OSError("API unavailable")

        with self.assertRaises(OSError):
            verify(REF, fail)

    def test_mutable_or_malformed_refs_fail(self) -> None:
        for ref in ["main", "v1.2.2", "a" * 39, "g" * 40, "a" * 40 + "?ref=main"]:
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                verify(ref, self.fetch)


if __name__ == "__main__":
    unittest.main()
