# project-6s · Repository cleanup for Codex

Old files are easy to remove. The work is finding what still depends on them and keeping the docs and tests useful after cleanup. `$project-6s` is a Codex skill for cleaning up a whole repository or just its documentation, assets, or tests.

Use it to find broken Markdown links and duplicate files, bring docs in line with the version they describe, and check that tests still catch regressions. For Git projects, the batch tool verifies changes in a separate copy and packages the before and after files for the maintainer. If removing a file breaks a previously working relative Markdown link, the tool stops before creating the handoff.

## Install

Copy `skills/project-6s/` into your personal Codex skills directory. The default is `~/.codex/skills/`. If you set `CODEX_HOME`, use its `skills/` subdirectory.

For a first install on Windows with GitHub CLI installed, run this in PowerShell.

```powershell
gh repo clone shihchengwei-lab/project-6s
cd project-6s
$skillHome = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
New-Item -ItemType Directory -Path $skillHome -Force | Out-Null
Copy-Item -LiteralPath './skills/project-6s' -Destination $skillHome -Recurse
```

To update, replace the installed skill folder with the copy from this repository. Check for local customizations before replacing it.

## Use in Codex

Ask in your own language. The skill replies in your language and keeps existing project docs in their original language unless you ask to change it.

```text
$project-6s Clean up this repository and bring the docs in line with the released version.
$project-6s Clean up the tests. Merge redundant cases and fix tests that still pass when the code is broken.
$project-6s Organize the source assets and archive the specified files outside the workspace.
```

Codex starts with the README and checks the setup, usage, maintenance, and design docs affected by the cleanup. For removals, it verifies the changes in a separate copy first. The person who controls writes to the target applies the verified changes and confirms any required archive is usable before removing the originals. See the [cleanup and recovery workflow](skills/project-6s/SKILL.md#handle-obsolete-copies-and-artifacts).

## Run the inventory script

The scripts require Python 3.11 or later and a Git repository with at least one commit. Run these examples from the root of this repository. The skill also supports manual review for projects without Git or a first commit.

```powershell
python -m pip install -r ./skills/project-6s/scripts/requirements.txt
python ./skills/project-6s/scripts/inventory.py . --base HEAD
```

The [dependency file](skills/project-6s/scripts/requirements.txt) installs the CommonMark parser used to check local links and images. Without it, inventory reports that link checks were skipped and still reports Git changes and duplicate files.

Inventory is read-only and returns JSON. Use `--base` to choose the commit, tag, or branch for the change list. The default is the commit current when the scan starts. The script also checks tracked files and unignored new files for broken links and duplicate content, even when the change list is empty. A zero exit code means the report was written. Check any skipped or unreadable files before acting on it.

Duplicate content is a lead for review. For example, this repository keeps a [license at the root](LICENSE) and an [identical copy in the skill folder](skills/project-6s/LICENSE) so the license travels with the installed skill.

## Verify a cleanup batch

`prepare` copies the full tree of a fixed Git commit into a batch folder outside the repository. It uses `HEAD` by default, or a revision you specify with `--revision`. Run it from the Git repository root and list every project-relative file the batch will add, change, or remove. Edit the returned `candidate` folder. Uncommitted changes stay in the original working tree.

```powershell
$batch = python ./skills/project-6s/scripts/batch.py prepare . "$env:TEMP/project-6s-batches" README.md | ConvertFrom-Json
# In $batch.candidate, change the first heading in README.md to the text below.
python ./skills/project-6s/scripts/batch.py verify $batch.batch --contains README.md "project-6s · Repository cleanup tools for Codex"
```

Give each changed file at least one built-in check. Use `--exists` for a file that should be present, `--absent` for a path that should be gone, and `--contains` for expected text. The tool automatically checks relative links and images in added or changed `.md` files. When a file or directory disappears, it also checks unchanged `.md` files for links that worked in the original tree but would break in the candidate. Use `--links` to check all relative targets in an additional Markdown file, including existing broken links.

The tool resolves URL dot segments before matching exact project paths. Raw HTML, external URLs, root-relative paths, query strings, and anchors are outside the check. If a required document cannot be parsed, a relative URL cannot be mapped to a project path, or a required target is missing, verification stops.

A successful run creates `runs/<run-id>/handoff/` with `manifest.json`, the original files under `before/`, and the candidate files under `after/`. The manifest records the checks, the Markdown parser and scope, and the link URLs and project paths it checked. If an interrupted run has no handoff, verify the candidate again to start a new run.

Use the skill's manual workflow for custom checks, symlinks, empty directories, paths that cannot be represented across platforms, case-only renames, or swaps between a file and a directory.

[MIT License](LICENSE)
