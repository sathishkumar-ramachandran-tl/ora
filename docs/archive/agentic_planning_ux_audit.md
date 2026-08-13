# Agentic Planning UX Audit

## Mandatory Screens Today

- Chat / Ask Ora: primary AI interaction surface and now the entry point for PlanProposal review/apply.
- Today / Schedule: still required for calendar inspection, focus blocks, and manual schedule edits.
- Project detail / board: required as the source of truth for real tasks, milestones, and sprint state after plan apply.
- Task detail: required for exact task status, ownership, due date, and dependencies.
- Module marketplace/review: still separate because module generation/install is not yet unified with PlanProposal.

## Jira-Style Surfaces That Should Become Secondary

- Dense board/task management screens should move behind project/detail context, not remain the default mental model.
- Milestone and sprint management should be reachable from project detail and plan application outcomes, not promoted as independent primary destinations.
- Raw tool-call pills should remain diagnostic/secondary; ActionCard and PlanCard are the user-facing AI operation surface.

## Operations That Can Move Into Chat / Actions

- Create project/task/milestone from a reviewed plan.
- Replan a scoped project.
- Mark task complete or update small task fields.
- Explain project status, blockers, next work, and partial plan application failures.

## Redundant Navigation Candidates

- Separate planning dialog and general chat should converge into scoped chat sessions.
- Project planning entry points should open Chat with `scope_level=project`.
- Task assistance should open Chat with `scope_level=task`.

## Incremental Migration Plan

1. Keep existing navigation stable.
2. Promote Chat / Ask Ora as the primary AI action surface.
3. Convert planning dialog copy and behavior to structured PlanProposal cards.
4. Add project/task chat launchers that pass explicit scope.
5. Move raw tool pills behind a developer/debug affordance after ActionCards cover major mutations.
6. Later, simplify home into Chat, Today, Active Work, and Recent Projects without removing detail views.
