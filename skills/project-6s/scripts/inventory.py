"""Collect read-only observations from a Git working tree."""

import argparse
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
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


def findings_for_links(root, file, text, changed):
    fence = ""
    for number, line in enumerate(text.splitlines(), 1):
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


def git_change_findings(root, base, head):
    queries = (
        ("committed", (base, head)),
        ("staged", ("--cached", head)),
        ("unstaged", ()),
    )
    for layer, revisions in queries:
        output = git(root, "diff", "--no-ext-diff", "--name-status", "--no-renames",
                     "-z", *revisions, "--")
        fields = output.split("\0")
        for status, path in zip(fields[::2], fields[1::2]):
            yield finding("change", path, {"layer": layer, "status": status})


@dataclass(frozen=True)
class FileStamp:
    identity: tuple[int, int]
    mode: int
    size: int
    modified_ns: int

    @classmethod
    def from_stat(cls, info):
        return cls((info.st_dev, info.st_ino), info.st_mode, info.st_size, info.st_mtime_ns)


def observe_file(file):
    try:
        if file.resolve() != file or file.is_symlink():
            return "skipped", "symbolic link or redirected path"
        info = file.lstat()
        if not stat.S_ISREG(info.st_mode):
            return "skipped", "not a regular file"
        return "regular", FileStamp.from_stat(info)
    except FileNotFoundError:
        return "missing", None
    except (OSError, RuntimeError) as error:
        return "unreadable", str(error)


class ScanChanged(Exception):
    """The file changed between enumeration and reading."""


def file_content(file, expected, markdown, hash_content):
    if observe_file(file) != ("regular", expected):
        raise ScanChanged(f"{file.name} changed before reading")
    with file.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if FileStamp.from_stat(before) != expected:
            raise ScanChanged(f"{file.name} was replaced before reading")
        content = stream.read() if markdown else None
        digest = None
        if hash_content:
            digest = (hashlib.sha256(content) if markdown else hashlib.file_digest(stream, "sha256")).hexdigest()
        after = os.fstat(stream.fileno())
        if FileStamp.from_stat(after) != expected or before.st_ctime_ns != after.st_ctime_ns:
            raise ScanChanged(f"{file.name} changed while reading")
    if observe_file(file) != ("regular", expected):
        raise ScanChanged(f"{file.name} changed after reading")
    return content, digest


def inventory(root, base):
    if Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve() != root:
        raise ValueError("project must be the Git working tree root")
    head = git(root, "rev-parse", "--verify", "HEAD^{commit}").strip()
    revision = head if base == "HEAD" else git(
        root, "rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}"
    ).strip()
    tracked = set(git(root, "ls-files", "--cached", "-z").split("\0")) - {""}
    untracked = set(git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0")) - {""}
    findings = list(git_change_findings(root, revision, head))
    findings.extend(
        finding("change", name, {"layer": "untracked", "status": "A"})
        for name in sorted(untracked - tracked)
    )
    changed = {item["file"] for item in findings}
    findings.extend(file_findings(root, tracked | untracked, changed))
    return {"report_type": "observations", "base_commit": revision, "head_commit": head,
            "findings": findings}


def file_findings(root, names, changed):
    files = {name: observe_file(root / name) for name in sorted(names)}
    by_size = defaultdict(int)
    for kind, evidence in files.values():
        if kind == "regular":
            by_size[evidence.size] += 1
    by_digest = defaultdict(list)
    for name, (kind, evidence) in files.items():
        if kind != "regular":
            yield finding(kind, name, evidence)
            continue
        file = root / name
        markdown = file.suffix.lower() == ".md"
        hash_content = by_size[evidence.size] > 1
        if not (markdown or hash_content):
            continue
        try:
            content, digest = file_content(file, evidence, markdown, hash_content)
            if digest is not None:
                by_digest[digest].append(name)
            if markdown:
                yield from findings_for_links(root, file, content.decode("utf-8-sig"), changed)
        except ScanChanged as error:
            yield finding("changed_during_read", name, str(error))
        except (OSError, UnicodeError, RuntimeError) as error:
            yield finding("unreadable", name, str(error))
    for group in by_digest.values():
        if len(group) > 1:
            yield finding("duplicate_content", group[0], group[1:])


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
    raise SystemExit(main())
