"""Collect read-only cleanup evidence from a Git working tree."""

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
from tempfile import TemporaryDirectory
from urllib.parse import unquote


DESTINATION = r"(?:<([^>\n]+)>|([^\s()<>]+))"
INLINE_LINK = re.compile(r"\]\(\s*" + DESTINATION + r"""(?:\s+["'][^\n]*?["'])?\s*\)""")
REFERENCE_LINK = re.compile(r"^ {0,3}\[[^\]]+\]:\s*" + DESTINATION)
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
CODE_SPAN = re.compile(r"(`+)(.*?)\1")


def git(root, *args, index=None):
    env = None if index is None else {**os.environ, "GIT_INDEX_FILE": str(index)}
    result = subprocess.run(
        ["git", "--no-optional-locks", *args], cwd=root, capture_output=True, env=env
    )
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout.decode("utf-8", errors="surrogateescape")


def findings_for_links(root, file, text, changed, targets):
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
            requested = file.parent / path
            if requested not in targets:
                targets[requested] = link_target(root, requested)
            target, exists = targets[requested]
            if not target.is_relative_to(root):
                continue
            relative = target.relative_to(root).as_posix()
            if not exists:
                yield finding("missing_link", file.relative_to(root).as_posix(), relative, number)
            elif relative in changed:
                yield finding("changed_reference", file.relative_to(root).as_posix(), relative, number)


def finding(kind, file, evidence, line=None):
    return {"kind": kind, "file": file, "line": line, "evidence": evidence}


def link_target(root, requested):
    target = requested.resolve()
    return target, target.is_relative_to(root) and target.exists()


def diff_fields(root, *revisions, index=None):
    output = git(root, "diff", "--no-ext-diff", "--name-status", "--no-renames",
                 "-z", *revisions, "--", index=index)
    return tuple(output.split("\0"))


def change_findings(fields, layer):
    for status, path in zip(fields[::2], fields[1::2]):
        yield finding("change", path, {"layer": layer, "status": status})


@dataclass(frozen=True)
class GitState:
    head: str
    tracked: frozenset[str]
    untracked: frozenset[str]
    staged: tuple[str, ...]
    unstaged: tuple[str, ...]

    @classmethod
    def read(cls, root, head, index):
        tracked = git(root, "ls-files", "--cached", "-z", index=index)
        untracked = git(root, "ls-files", "--others", "--exclude-standard", "-z", index=index)
        return cls(
            head,
            frozenset(tracked.split("\0")) - {""},
            frozenset(untracked.split("\0")) - {""},
            diff_fields(root, "--cached", head, index=index),
            diff_fields(root, index=index),
        )


def read_index(index):
    try:
        return index.read_bytes()
    except FileNotFoundError:
        return None


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
    """A read no longer agrees with the observed working-tree state."""


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
    return content, digest


def inventory(root, base):
    if Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve() != root:
        raise ValueError("project must be the Git working tree root")
    head = git(root, "rev-parse", "--verify", "HEAD^{commit}").strip()
    revision = head if base == "HEAD" else git(
        root, "rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}"
    ).strip()
    report = {"base_commit": revision, "head_commit": head}
    live_index = Path(git(root, "rev-parse", "--path-format=absolute", "--git-path", "index").rstrip("\r\n"))
    try:
        index_bytes = read_index(live_index)
        with TemporaryDirectory(prefix="project-6s-index-") as directory:
            index = Path(directory) / "index"
            if index_bytes is not None:
                index.write_bytes(index_bytes)
            state = GitState.read(root, head, index)
            findings = scan(root, state, revision)
            if GitState.read(root, head, index) != state:
                raise ScanChanged("working-tree status changed during the scan")
        if git(root, "rev-parse", "--verify", "HEAD^{commit}").strip() != head or read_index(live_index) != index_bytes:
            raise ScanChanged("HEAD or index changed during the scan")
    except ScanChanged as error:
        return {**report, "status": "unstable", "reason": str(error), "findings": []}
    partial = any(item["kind"] in ("unreadable", "skipped") for item in findings)
    return {**report, "status": "partial" if partial else "complete", "findings": findings}


def scan(root, state, revision):
    tracked = state.tracked
    findings = list(change_findings(diff_fields(root, revision, state.head), "committed"))
    findings.extend(change_findings(state.staged, "staged"))
    findings.extend(change_findings(state.unstaged, "unstaged"))
    findings.extend(
        finding("change", name, {"layer": "untracked", "status": "A"})
        for name in sorted(state.untracked - tracked)
    )
    changed = {item["file"] for item in findings}
    files = {name: observe_file(root / name) for name in sorted(tracked | state.untracked)}
    by_size = defaultdict(int)
    for kind, evidence in files.values():
        if kind == "regular":
            by_size[evidence.size] += 1
    by_digest = defaultdict(list)
    targets = {}
    for name, (kind, evidence) in files.items():
        if kind != "regular":
            if kind != "missing":
                findings.append(finding(kind, name, evidence))
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
                findings.extend(findings_for_links(root, file, content.decode("utf-8-sig"), changed, targets))
        except (OSError, UnicodeError, RuntimeError) as error:
            findings.append(finding("unreadable", name, str(error)))
    for group in by_digest.values():
        if len(group) > 1:
            findings.append(finding("duplicate_content", group[0], group[1:]))
    for name, original in files.items():
        if observe_file(root / name) != original:
            raise ScanChanged(f"{name} changed during the scan")
    for path, original in targets.items():
        if link_target(root, path) != original:
            raise ScanChanged(f"{path} changed during the scan")
    return findings


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
    return 2 if report["status"] == "unstable" else 0


if __name__ == "__main__":
    raise SystemExit(main())
