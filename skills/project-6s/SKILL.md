---
name: project-6s
license: MIT
description: "Use for 6S cleanup of a software project or its assets, documentation, or tests. Remove obsolete artifacts, update current documentation, and isolate required archives while preserving product behavior."
---

# Project 6S

Clean up the requested scope so the next maintainer can find the authoritative sources and follow the current procedures.

Use the user's requested language for replies and reports. Otherwise, follow the language of the user's own messages. If they invoke the skill with its default prompt, use the language already established in the conversation. When updating existing project docs, keep each document's language unless the user asks to change it.

## Set the scope

- Read the project's collaboration rules. Choose the version the docs should describe and establish the cleanup scope, behavior to preserve, and verification steps.
- If Python 3.11 or later is available and the repository has a Git commit, run [inventory](scripts/inventory.py) with `python <script-path> <repository-root> --base <revision>`. With no `--base`, it uses the commit current at the start of the scan. Keep the returned `base_commit` for reruns.
- Inventory reports observations from individual reads. Use changes to locate references, then review broken links, duplicate content, and skipped or unreadable files. Judge duplicates by their role. Link checks require the [Markdown parser](scripts/requirements.txt). If inventory skips them, check the affected docs separately.
- Use the project's existing builds, tests, and asset lists. Fix and verify one representative case before repeating the same change across the project.
- Commit, push, deploy, or publish as directed by the user.

## Align project documentation

- For a full cleanup, start from the README and review setup, usage, maintenance, and design docs within scope, including existing translations. For a scoped cleanup or a pre-commit check, review the README and docs that describe affected behavior. Bring stale instructions within scope up to date even when the current change did not cause them.
- Verify claims against the version each document describes. Trace references back to the implementation, specs, or verification results. Check purpose, requirements, commands, outputs, defaults, and limits. Preserve conditions that affect a reader's decisions in any summaries or existing translations you update.
- Run representative documented procedures and verify the links. Flag any outstanding checks that affect use or handoff.

## Handle obsolete copies and artifacts

Group interdependent files and references into one batch. Use inventory to choose what to inspect. The person doing the cleanup checks each item's purpose, references, license, recovery source, and target working directory.

Prepare and verify moves or removals in an isolated copy you control. Treat any working directory that another person, session, or background tool can write to as shared. Keep control of writes throughout any operation that removes an existing path.

For Git projects, the [batch tool](scripts/batch.py) builds a candidate from the full tree of a fixed commit. Both `prepare` and `verify` check the source repository root. Declare the files to change, then edit the `candidate` directory. Run the built-in checks with `verify` and hand off the package for the selected `run_id`.

The tool checks relative CommonMark links and images in added or changed Markdown. If paths disappear, it also checks that previously working relative references in unchanged Markdown still work. It uses the same resolved project path in both trees and stops if it cannot establish a target within the project. Use `--links` to check all in-scope relative targets in an additional file. The package records what was checked. Check raw HTML, external URLs, and anchors separately when the task requires them.

Use the manual isolation workflow below when the required checks exceed the tool's scope, or the batch needs an uncommitted baseline, file/directory swaps, case-only renames, conflicting or nonportable names, empty directories, or symlinks.

If you cannot control writes to the target, give its maintainer the verified candidate and its batch record. If any handoff material is missing, report the batch stage and what remains to be done.

### Batch record

- Assign a batch ID. Before the first write to the target, record the original state, expected result, and recovery source for every affected path and reference in one local record. Include actual uncommitted content, originally absent paths, and archive destinations outside the repository.
- Tie that record to the original revision or content, the verified candidate revision or file hashes, expected removals and archives, and the checks and results. Include conditions that affect verification, such as active settings, tool versions, or external data. If the candidate or those conditions change, verify again.
- Use a batch-specific archive destination confirmed to be empty for new archives. If reusing an archive, record its original state, verify its contents and access, and treat it as read-only.

| Stage | Entry conditions and next action |
|---|---|
| Inventory | Check code references, manual workflows, licenses, source material, and how to rebuild it. If purpose, license, recovery source, or archive destination is unresolved, keep the batch intact and record what needs checking. |
| Prepare | In the isolated copy, put the authoritative source in place, update references and docs, then remove the old path. Record the original and candidate in the [batch record](#batch-record). |
| Verified | The fixed candidate represents the intended final state and passes [final verification](#verify-and-wrap-up). Record the results and conditions. Run the checks against the candidate. If checks fail or docs need edits, return to preparation and verify again. |
| Applying | The person who controls writes checks authorization, the original state, the recovery source, the candidate, and the verification conditions at the target. Return to preparation if any differ or cannot be confirmed. Record that application is in progress and identify the verification record. For a tool-generated handoff, record its batch ID, run ID, and manifest hash. Apply and recover from that same record. Confirm required archives are readable and accessible before removing source paths. For archives inside the project, also verify isolation from search and model reads. |
| Confirm or recover | Enter this stage on failure, interruption, loss of write control, uncertain archive results, or when a handoff record still says application is in progress. Follow the recovery steps below. |
| Finalized | While you still control writes, check that the verification conditions hold and that paths, contents, references, and archives match the batch record. Verify affected workflows through their actual entry points. Record finalization before clearing recovery-only material. If a check fails, move to recovery. If interrupted after finalization, check and clear the remaining recovery material. |

On every recovery attempt, including after an interruption during recovery, recheck the actual state against the batch record. If an archive operation lost its acknowledgment, confirm at the destination that the batch's write completed or ended and check the original destination state. Keep the source and recovery material while the result is uncertain, even if the archive is not visible yet.

Skip items already confirmed to match the original. Restore only changes attributable to this batch while you control writes. Confirm the restored original is usable before clearing any archive copy created by the batch. If the state is unclear, writes are uncontrolled, or other edits conflict, preserve the current state and recovery material and report what needs confirmation. Return to preparation once the whole batch is confirmed restored.

## 6S checklist

Apply the checks relevant to the scope.

| Item | What to check |
|---|---|
| Sort | Unneeded intermediate files, outdated copies, and rejected assets have been dealt with. |
| Set in order | Each piece of information has a clear home and one authoritative source. |
| Shine | Broken references and redundant settings are fixed. Tests cover the behavior that must be preserved. |
| Standardize | Current docs consolidate duplicates, replace stale instructions, and remove completed tasks while retaining procedures, design decisions, constraints, and rationale that still matter. |
| Sustain | Existing checks are reused. Any new rule prevents a problem observed during the cleanup. |
| Safety | Check absolute paths, project boundaries, symlink targets, retention requirements, and current authorization. Protect licenses, authoritative sources, user data, and unrelated uncommitted changes. |

For test cleanup, read [test cleanup](references/test-cleanup.md).

## Verify and wrap up

- Finish [aligning project documentation](#align-project-documentation) and verify the affected references and procedures.
- Run affected builds and tests using the project's existing pass criteria. Put rebuild output in an isolated location. Diagnose failures and fix problems within scope.
- If inventory is available, rerun it with the first report's `base_commit` to check affected paths and references.
- Clear temporary verification output, scripts, and caches.
- Report what changed, what passed, and any issue that still affects use or handoff. Link to existing records where useful.
