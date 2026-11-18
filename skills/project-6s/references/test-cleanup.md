# Test cleanup

## Identify what each case protects

- Keep coverage for observable behavior, failure paths, input boundaries, data compatibility, type rejection, and integration across modules. Unit tests cover local logic. Integration tests cover how modules work together. Before merging or deleting a case, identify which remaining case covers the behavior that must stay.
- If reading the remaining case leaves its ability to catch the target fault unclear, [introduce the fault and verify it fails](#verify-the-change) before removing the original case.
- Check whether fixed values encode compatibility requirements, especially for external formats, historical links, seeds, serialized data, and public APIs. When consolidating similar invalid inputs, distinguish the parsing, encoding, or security boundary exercised by each.
- Prioritize cases that calculate expectations by copying the implementation line by line, only exercise test helpers, or depend on wording or component internals without a requirement.

## Fix false passes and test interference

- Name tests for what they observe, such as "checks audio parameters" or "server renders button markup." Test clicks, focus, or touch through an entry point that exercises the interaction.
- Look for ways assertions can be bypassed or pass for the wrong reason. Check loops over empty collections, async assertions that are never awaited, searches returning `-1`, loose truthiness checks, and fixtures that miss the intended branch.
- When checking repeatability, use multi-step sequences, independent instances, or fixed compatibility fixtures as needed. Give simulations and searches fixed inputs, explicit bounds, and a failure message when the scenario is not found. Prefer a real replay or a small existing fixture.
- Share setup that is genuinely duplicated while keeping each case's data and dependencies visible. Restore test doubles, environment variables, and clocks, and clear temporary resources. Use the project's existing type-checking entry point for type rejection cases.

## Verify the change

Run the affected cases first, then the full checks required by the project. If you find a product defect, keep the reproducing case and explain the impact. Handle the defect within the task's scope.

To prove a case catches a specific fault, introduce that fault in an isolated copy, such as clearing the options, skipping a completion branch, or keeping an animation running. Run the tests from that copy and keep output there or in isolated temporary storage. Confirm the intended assertion fails, then remove the fault and rerun. If the isolated copy cannot reproduce the required conditions, keep the original case and report the verification gap.
