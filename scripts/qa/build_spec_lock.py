#!/usr/bin/env python3
"""Build a deterministic spec.lock.json from the profile and its referenced artifacts.

Reads spec/profiles/default.yaml, resolves all references (schemas, contracts,
rulesets), extracts each file's version and sha256, and writes a lock file.

Exit code 1 if any referenced file is missing or lacks a version field.
"""

import argparse
import hashlib
import json
import pathlib
import sys
import yaml


PROFILE_PATH = "spec/profiles/default.yaml"
LOCK_VERSION = "1.0.0"

KIND_MAP = {
    "schemas": "schema",
    "contracts": "contract",
    "rulesets": "ruleset",
}


def sha256_of(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def read_version(path: pathlib.Path) -> str:
    """Return the top-level 'version' field from a JSON or YAML file."""
    raw = path.read_bytes()
    suffix = path.suffix.lower()

    if suffix == ".json":
        data = json.loads(raw)
    elif suffix in (".yaml", ".yml"):
        data = yaml.safe_load(raw)
    else:
        raise SystemExit(f"ERROR: unsupported file type {suffix} for {path}")

    if not isinstance(data, dict) or "version" not in data:
        raise SystemExit(f"'version' field missing in {path}")

    return str(data["version"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build spec.lock.json")
    parser.add_argument(
        "--out",
        default="frozen/v1.0.0/spec.lock.json",
        help="Output path (default: frozen/v1.0.0/spec.lock.json)",
    )
    args = parser.parse_args()

    root = pathlib.Path.cwd()
    profile_path = root / PROFILE_PATH

    # --- Load profile --------------------------------------------------------
    if not profile_path.is_file():
        print(f"ERROR: profile not found: {profile_path}", file=sys.stderr)
        sys.exit(1)

    profile_raw = profile_path.read_bytes()
    profile = yaml.safe_load(profile_raw)

    if "version" not in profile:
        print(f"ERROR: 'version' field missing in {PROFILE_PATH}", file=sys.stderr)
        sys.exit(1)

    profile_block = {
        "path": PROFILE_PATH,
        "id": profile.get("id", ""),
        "version": str(profile["version"]),
        "sha256": sha256_of(profile_raw),
    }

    # --- Resolve artifacts ---------------------------------------------------
    errors: list[str] = []
    artifacts: list[dict] = []

    for section, kind in sorted(KIND_MAP.items()):
        entries = profile.get(section, {})
        if not isinstance(entries, dict):
            continue

        for artifact_id, rel_path in sorted(entries.items()):
            file_path = root / rel_path

            if not file_path.is_file():
                errors.append(f"file not found: {rel_path} (referenced as {artifact_id})")
                continue

            file_raw = file_path.read_bytes()

            try:
                version = read_version(file_path)
            except SystemExit as exc:
                errors.append(str(exc))
                continue

            artifacts.append({
                "kind": kind,
                "id": artifact_id,
                "path": rel_path,
                "version": version,
                "sha256": sha256_of(file_raw),
            })

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)

    # --- Write lock file -----------------------------------------------------
    lock = {
        "lock_version": LOCK_VERSION,
        "profile": profile_block,
        "artifacts": artifacts,
    }

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(lock, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"OK  spec.lock.json written to {out_path} ({len(artifacts)} artifacts)")


if __name__ == "__main__":
    main()
