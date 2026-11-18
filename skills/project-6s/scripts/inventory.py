"""Collect read-only cleanup evidence from a Git working tree."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote


DESTINATION = r"(?:<([^>\n]+)>|([^\s()<>]+))"
INLINE_LINK = re.compile(r"\]\(\s*" + DESTINATION + r"""(?:\s+["'][^\n]*?["'])?\s*\)""")
REFERENCE_LINK = re.compile(r"^ {0,3}\[[^\]]+\]:\s*" + DESTINATION)
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
CODE_SPAN = re.compile(r"(`+)(.*?)\1")


def git(root, *args):
    result = subprocess.run(
        ["git", "--no-optional-locks", *args], cwd=root, capture_output=True
    )
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout.decode("utf-8", errors="surrogateescape")


def findings_for_links(root, file, changed):
    fence = ""
    for number, line in enumerate(file.read_text(encoding="utf-8-sig").splitlines(), 1):
        marker = FENCE.match(line)
        if fence:
            if marker and marker[1].startswith(fence) and not marker[2].strip():
                fence = ""
            continue
        if marker:
            fence = marker[1]
            continue
        line = CODE_SPAN.sub("", line)
        links = list(INLINE_LINK.finditer(line))
        reference = REFERENCE_LINK.match(line)
        if reference:
            links.append(reference)
        for link in links:
            destination = link[1] or link[2]
            path = unquote(re.split(r"[?#]", destination, maxsplit=1)[0])
            if not path or path.startswith(("/", "\\")) or ":" in path:
                continue
            target = (file.parent / path).resolve()
            if not target.is_relative_to(root):
                continue
            relative = target.relative_to(root).as_posix()
            if not target.exists():
                yield finding("missing_link", file.relative_to(root).as_posix(), relative, number)
            elif relative in changed:
                yield finding("changed_reference", file.relative_to(root).as_posix(), relative, number)


def finding(kind, file, evidence, line=None):
    return {"kind": kind, "file": file, "line": line, "evidence": evidence}


def changes_from_diff(root, layer, *revisions):
    fields = git(root, "diff", "--no-ext-diff", "--name-status", "--no-renames",
                 "-z", *revisions, "--").split("\0")
    for status, path in zip(fields[::2], fields[1::2]):
        yield finding("change", path, {"layer": layer, "status": status})


def inventory(root, base):
    if Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve() != root:
        raise ValueError("project must be the Git working tree root")
    revision = git(root, "rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}").strip()
    tracked = set(git(root, "ls-files", "--cached", "-z").split("\0")) - {""}
    untracked = set(git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0")) - {""}
    findings = list(changes_from_diff(root, "committed", revision, "HEAD"))
    findings.extend(changes_from_diff(root, "staged", "--cached", "HEAD"))
    findings.extend(changes_from_diff(root, "unstaged"))
    findings.extend(
        finding("change", name, {"layer": "untracked", "status": "A"})
        for name in sorted(untracked - tracked)
    )
    changed = {item["file"] for item in findings}
    by_size = defaultdict(list)
    for name in sorted(tracked | untracked):
        file = root / name
        try:
            if file.resolve() != file or not file.is_file():
                continue
            by_size[file.stat().st_size].append(name)
            if file.suffix.lower() == ".md":
                findings.extend(findings_for_links(root, file, changed))
        except (OSError, UnicodeError, RuntimeError) as error:
            findings.append(finding("unreadable", name, str(error)))
    for names in by_size.values():
        if len(names) < 2:
            continue
        by_digest = defaultdict(list)
        for name in names:
            try:
                with (root / name).open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                by_digest[digest].append(name)
            except OSError as error:
                findings.append(finding("unreadable", name, str(error)))
        for group in by_digest.values():
            if len(group) > 1:
                findings.append(finding("duplicate_content", group[0], group[1:]))
    return {"base_commit": revision, "findings": findings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Git working tree root")
    parser.add_argument("--base", default="HEAD", help="Git commit, tag, or branch (default: HEAD)")
    args = parser.parse_args()
    try:
        report = inventory(args.project.resolve(strict=True), args.base)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"inventory: {error}\n")
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
