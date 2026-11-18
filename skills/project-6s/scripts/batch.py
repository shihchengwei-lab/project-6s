"""Prepare a cleanup batch from a Git commit and verify its candidate."""

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory, gettempdir
from unicodedata import normalize
from uuid import uuid4

sys.dont_write_bytecode = True
from inventory import FileStamp, observe_file
from markdown_paths import MarkdownPaths


def plain_path(path):
    text = str(path)
    if os.name == "nt" and text.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + text[8:])
    if os.name == "nt" and text.startswith("\\\\?\\"):
        return Path(text[4:])
    return path


def filesystem_path(path):
    if os.name != "nt":
        return path
    text = str(plain_path(path))
    if text.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + text[2:])
    return Path("\\\\?\\" + text)


def absolute_path(path, *, strict=False):
    return filesystem_path(path.absolute()).resolve(strict=strict)


def exact_name(value):
    path = PurePosixPath(value)
    if (not path.parts or path.is_absolute() or path.as_posix() != value
            or any(part.casefold() in ("..", ".git") or part != part.rstrip(". ")
                   or re.search(r'[\\:*?"<>|\x00-\x1f]', part)
                   or PureWindowsPath(part).is_reserved() for part in path.parts)):
        raise ValueError(f"unsupported project-relative path: {value!r}; use the manual isolation workflow")
    return value


def argument_name(value):
    return exact_name(PurePosixPath(value.replace("\\", "/")).as_posix())


def path_key(name):
    return normalize("NFC", name).casefold()


def file_namespace(files):
    """Index exact spellings and kinds by their portable path identity."""
    entries = {}
    for name in sorted(files):
        path = PurePosixPath(exact_name(name))
        locations = [(path, "file")]
        locations.extend((parent, "directory") for parent in path.parents)
        for child, kind in locations:
            spelling = child.as_posix()
            entry = spelling, kind
            previous = entries.setdefault(path_key(spelling), entry)
            if previous != entry:
                raise ValueError(
                    f"conflicting paths: {previous[0]!r} ({previous[1]}) and "
                    f"{spelling!r} ({kind}); use the manual isolation workflow"
                )
    return entries


def check_transition(original, candidate):
    for key in sorted(original.keys() & candidate.keys()):
        previous, current = original[key], candidate[key]
        if previous != current:
            raise ValueError(
                f"unsupported path transition: {previous[0]!r} ({previous[1]}) to "
                f"{current[0]!r} ({current[1]}); use the manual isolation workflow"
            )


def git(project, *args, output=subprocess.PIPE):
    environment = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith("GIT_")}
    environment.update(GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(
        ["git", "--no-optional-locks", "--no-replace-objects", *args],
        cwd=plain_path(project), env=environment, stdout=output, stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def git_worktree_root(path):
    project = absolute_path(path, strict=True)
    root = git(project, "rev-parse", "--show-toplevel").decode("utf-8").strip()
    if absolute_path(Path(root), strict=True) != project:
        raise ValueError("project must be the Git working tree root")
    return project


def require_outside_worktree(path, project):
    if path.is_relative_to(project) or any(
        (parent / ".git").exists() for parent in (path, *path.parents)
    ):
        raise ValueError("batch storage must be outside Git working trees")


def write_record(path, record):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def copy_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    hash_value = hashlib.sha256()
    with target.open("xb") as output:
        while chunk := source.read(1024 * 1024):
            hash_value.update(chunk)
            output.write(chunk)
    return hash_value.hexdigest()


def commit_files(project, commit, destination):
    blobs = {}
    directories = set()
    for entry in git(project, "ls-tree", "--full-tree", "-r", "-t", "-z", commit).split(b"\0")[:-1]:
        descriptor, raw_name = entry.split(b"\t", 1)
        mode, object_type, digest = descriptor.decode("ascii").split()
        name = exact_name(raw_name.decode("utf-8"))
        if object_type == "tree":
            directories.add(name)
            continue
        if object_type != "blob" or mode not in ("100644", "100755"):
            raise ValueError(f"the selected commit contains an unsupported entry: {name}")
        blobs[name] = (mode, digest)
    file_parents = {name for name, kind in file_namespace(blobs).values() if kind == "directory"}
    if directories - file_parents:
        raise ValueError(f"the selected commit contains an empty directory: {min(directories - file_parents)}")

    manifest = {}
    for name, (mode, digest) in blobs.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            git(project, "cat-file", "blob", digest, output=output)
        if os.name != "nt":
            target.chmod(0o755 if mode == "100755" else 0o644)
        with target.open("rb") as stream:
            manifest[name] = {"mode": mode, "sha256": hashlib.file_digest(stream, "sha256").hexdigest()}
    if snapshot(destination, None, manifest) != manifest:
        raise ValueError("the checkout does not faithfully represent the selected Git commit")
    return manifest


def candidate_files(root):
    def raise_error(error):
        raise error

    if root.resolve() != root or not root.is_dir():
        raise ValueError("candidate directory is unavailable or redirected")
    for directory, subdirectories, files in os.walk(root, onerror=raise_error):
        parent = Path(directory)
        relative_parent = parent.relative_to(root)
        for name in subdirectories:
            exact_name((PurePosixPath(relative_parent.as_posix()) / name).as_posix())
            child = parent / name
            if child.is_symlink() or child.resolve() != child:
                raise ValueError(f"redirected directory: {child.relative_to(root)}")
        if parent != root and not (subdirectories or files):
            raise ValueError(f"empty directories are outside the batch format: {parent.relative_to(root)}")
        for leaf in sorted(files):
            yield exact_name((PurePosixPath(relative_parent.as_posix()) / leaf).as_posix())


def snapshot(root, destination, original):
    """Capture the exact file tree supported by this batch format."""
    names = sorted(candidate_files(root))
    file_namespace(names)
    manifest = {}
    for name in names:
        file = root / name
        kind, observed = observe_file(file)
        if kind != "regular":
            raise ValueError(f"unsupported candidate file: {name} ({kind})")
        with file.open("rb") as stream:
            opened = FileStamp.from_stat(os.fstat(stream.fileno()))
            if not observed.matches_open_file(opened):
                raise ValueError(f"candidate file changed before capture: {name}")
            if destination is None:
                sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
            else:
                sha256 = copy_file(stream, destination / name)
            if FileStamp.from_stat(os.fstat(stream.fileno())) != opened:
                raise ValueError(f"candidate file changed during capture: {name}")
        if observe_file(file) != ("regular", observed):
            raise ValueError(f"candidate file changed during capture: {name}")
        mode = original.get(name, {}).get("mode", "100644") if os.name == "nt" else (
            "100755" if stat.S_IMODE(observed.mode) & stat.S_IXUSR else "100644"
        )
        if destination is not None and os.name != "nt":
            (destination / name).chmod(0o755 if mode == "100755" else 0o644)
        manifest[name] = {"mode": mode, "sha256": sha256}
    return manifest


def prepare(project, store, revision, paths):
    project = git_worktree_root(project)
    store = absolute_path(store)
    require_outside_worktree(store, project)
    declared = sorted({argument_name(path) for path in paths})
    commit = git(project, "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}").decode().strip()
    batch_id = uuid4().hex
    store.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".prepare-", dir=store) as directory:
        draft = Path(directory)
        candidate = draft / "candidate"
        candidate.mkdir()
        originals = commit_files(project, commit, candidate)
        check_transition(file_namespace(originals), file_namespace(declared))
        write_record(draft / "batch.json", {
            "batch_id": batch_id,
            "project": str(plain_path(project)),
            "commit": commit,
            "paths": declared,
            "declared_originals": {path: originals.get(path) for path in declared},
        })
        batch = store / batch_id
        draft.rename(batch)
    return {"batch_id": batch_id, "commit": commit, "batch": str(plain_path(batch)),
            "candidate": str(plain_path(batch / "candidate"))}


def verify_markdown(root, files, original_namespace, candidate_namespace, changes, requested):
    documents = {name for name in files if name.lower().endswith(".md")}
    changed = documents.intersection(changes)
    complete = changed | requested
    original_paths = dict(original_namespace.values())
    candidate_paths = dict(candidate_namespace.values())
    original_paths["."] = candidate_paths["."] = "directory"
    removed = original_paths.keys() - candidate_paths.keys()
    # A remaining path keeps its exact spelling and kind after check_transition.
    # With no removals, adding paths cannot invalidate an unchanged reference.
    compare = documents - complete if removed else set()
    if not (complete or compare):
        return None

    markdown = MarkdownPaths()
    checked = {}
    retained = {}
    for name in sorted(complete | compare):
        targets = []
        try:
            text = (root / name).read_text(encoding="utf-8-sig")
            for line, target in markdown.project_targets(name, text):
                if name in compare and not target.matches_kind(original_paths.get(target.path)):
                    continue
                if not target.matches_kind(candidate_paths.get(target.path)):
                    location = f"block starting on line {line}: " if line is not None else ""
                    reason = "link target lost from the baseline" if name in compare else "missing exact link target"
                    raise ValueError(f"{location}{reason}: {target.href} (resolved to {target.path})")
                targets.append({"block_start_line": line, "href": target.href, "path": target.path,
                                "directory_required": target.directory_required})
        except ValueError as error:
            raise ValueError(f"{name}: {error}") from error
        (retained if name in compare else checked)[name] = targets

    return {
        **markdown.evidence(),
        "target_resolution": "normalize relative URL dot segments, then match exact project paths and required directories",
        "documents": checked,
        "unchanged_documents_compared": retained,
        "removed_paths": sorted(removed),
    }


def check_candidate(root, files, original_namespace, candidate_namespace, checks, changes):
    unchecked = set(changes) - {check["path"] for check in checks}
    if unchecked:
        raise ValueError(f"changed files without a check: {', '.join(sorted(unchecked))}")
    requested = set()
    for check in checks:
        name = check["path"]
        rule = check["check"]
        if rule == "absent":
            if path_key(name) in candidate_namespace:
                raise ValueError(f"expected absent path: {name}")
            continue
        if name not in files:
            raise ValueError(f"expected a regular file: {name}")
        if rule == "exists":
            continue
        if rule == "links":
            if not name.lower().endswith(".md"):
                raise ValueError(f"Markdown link check requires a .md file: {name}")
            requested.add(name)
        elif rule == "contains" and check["text"] not in (root / name).read_text(encoding="utf-8-sig"):
            raise ValueError(f"expected text not found: {name}")

    verification = {"type": "builtin", "checks": checks}
    markdown = verify_markdown(root, files, original_namespace, candidate_namespace, changes, requested)
    if markdown is not None:
        verification["markdown"] = markdown
    return verification


def verify(batch, checks):
    batch = absolute_path(batch, strict=True)
    record = json.loads((batch / "batch.json").read_text(encoding="utf-8"))
    if record["batch_id"] != batch.name or not re.fullmatch(r"[0-9a-f]{32}", batch.name):
        raise ValueError("batch ID does not match the directory")
    original_project = git_worktree_root(Path(record["project"]))
    require_outside_worktree(batch, original_project)
    commit = record["commit"]
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
        raise ValueError("batch requires a fixed Git commit ID")
    if git(original_project, "cat-file", "-t", commit).strip() != b"commit":
        raise ValueError("batch source is not a Git commit")
    declared = {exact_name(path) for path in record["paths"]}

    run_id = uuid4().hex
    run = batch / "runs" / run_id
    if (batch / "runs").resolve() != batch / "runs":
        raise ValueError("redirected run directory")
    run.mkdir(parents=True)
    write_record(run / "attempt.json", {"run_id": run_id, "batch_id": batch.name, "source": {
        "project": str(plain_path(original_project)), "commit": commit,
    }, "checks": checks})
    print(f"Run: {run_id} ({plain_path(run)})", file=sys.stderr, flush=True)

    temporary_root = absolute_path(Path(gettempdir()), strict=True)
    require_outside_worktree(temporary_root, original_project)
    with TemporaryDirectory(prefix=".handoff-", dir=run) as staging, ExitStack() as snapshots:
        draft = Path(staging)
        workspace = Path(snapshots.enter_context(TemporaryDirectory(prefix="6s-", dir=temporary_root)))
        original, candidate = workspace / "original", workspace / "candidate"
        original.mkdir()
        candidate.mkdir()
        originals = commit_files(original_project, commit, original)
        if {path: originals.get(path) for path in declared} != record["declared_originals"]:
            raise ValueError("declared originals do not match the selected Git commit")
        captured = snapshot(batch / "candidate", candidate, originals)
        if snapshot(candidate, None, originals) != captured:
            raise ValueError("isolated candidate does not match the snapshot")
        original_namespace = file_namespace(originals)
        candidate_namespace = file_namespace(captured)
        check_transition(original_namespace, file_namespace(declared))
        check_transition(original_namespace, candidate_namespace)

        changes = sorted(name for name in originals.keys() | captured.keys()
                         if originals.get(name) != captured.get(name))
        if not changes:
            raise ValueError("the candidate has no changes")
        undeclared = set(changes) - declared
        if undeclared:
            raise ValueError(f"changes outside the batch: {', '.join(sorted(undeclared))}")
        verification = check_candidate(
            candidate, captured, original_namespace, candidate_namespace, checks, changes,
        )
        if snapshot(batch / "candidate", None, originals) != captured:
            raise ValueError("the candidate changed during verification; run verify again")

        before, after = draft / "before", draft / "after"
        before.mkdir()
        after.mkdir()
        for name in changes:
            for state, tree, output in ((originals, original, before), (captured, candidate, after)):
                if name in state:
                    with (tree / name).open("rb") as stream:
                        if copy_file(stream, output / name) != state[name]["sha256"]:
                            raise ValueError(f"handoff bytes do not match the verified record: {name}")
                    if os.name != "nt":
                        (output / name).chmod(0o755 if state[name]["mode"] == "100755" else 0o644)
        write_record(draft / "manifest.json", {
            "batch_id": batch.name,
            "run_id": run_id,
            "source": {"project": str(plain_path(original_project)), "commit": commit},
            "changes": {name: {"before": originals.get(name), "after": captured.get(name)}
                        for name in changes},
            "original_inputs": originals,
            "verified_inputs": captured,
            "verification": verification,
        })
        snapshots.close()
        handoff = run / "handoff"
        draft.rename(handoff)
    return {"batch_id": batch.name, "run_id": run_id, "handoff": str(plain_path(handoff)),
            "files": len(changes)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    preparation = commands.add_parser("prepare", help="create an editable copy of a fixed Git commit")
    preparation.add_argument("project", type=Path)
    preparation.add_argument("store", type=Path)
    preparation.add_argument("paths", nargs="+")
    preparation.add_argument("--revision", default="HEAD")
    verification = commands.add_parser("verify", help="run built-in checks and publish a handoff")
    verification.add_argument("batch", type=Path)
    for name in ("exists", "absent", "links"):
        verification.add_argument(f"--{name}", action="append", default=[], metavar="PATH")
    verification.add_argument("--contains", nargs=2, action="append", default=[], metavar=("PATH", "TEXT"))
    args = parser.parse_args()
    try:
        if args.operation == "prepare":
            result = prepare(args.project, args.store, args.revision, args.paths)
        else:
            checks = [{"check": rule, "path": argument_name(path)}
                      for rule in ("exists", "absent", "links") for path in getattr(args, rule)]
            for path, value in args.contains:
                if not value:
                    raise ValueError("the expected text must not be empty")
                checks.append({"check": "contains", "path": argument_name(path), "text": value})
            if not checks:
                raise ValueError("provide one or more built-in checks")
            result = verify(args.batch, checks)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        parser.exit(1, f"batch: {error}\n")
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
