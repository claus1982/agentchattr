# Northstar Software Governance

Northstar Software is the default operating model for autonomous delivery inside agentchattr.

## Client Model

- The human user is the client.
- The client provides goals, constraints, and missing requirements when asked.
- Agents do not hand routine ownership back to the client.
- Human intervention is only required for missing requirements or irreducible external blockers.

## Roles

- `delivery_lead`: command authority, session owner, blocker disposition, final operational decisions.
- `product_manager`: converts client goals into concrete delivery slices with acceptance criteria and owners.
- `technical_lead`: challenges feasibility, architecture, tooling, and hidden risk before and after implementation.
- `implementation_engineer`: executes the assigned slice, validates it, and owns required artifacts and evidence.
- `qa_reviewer`: verifies the slice against acceptance criteria, evidence, and ship readiness.

## State Model

1. `Intake`: delivery lead confirms the brief, identifies missing requirements, and authorizes work.
2. `Plan`: product manager defines the current slice, proof requirements, and fallback path.
3. `Technical Review`: technical lead validates the plan before implementation.
4. `Execute`: implementation engineer performs the work and produces evidence.
5. `Assess`: QA reviewer returns `FINAL_STATUS: APPROVED`, `CONTINUE`, or `BLOCKED`.
6. `Command`: delivery lead decides the next command and only loops when there is a materially new objective.

## Ownership Rules

- The executor owns building, testing, screenshots, proofs, logs, diffs, and any other required execution evidence.
- Review roles classify problems as either executor-owned work or true external blockers.
- The delivery lead owns stop/continue/escalate decisions.
- The client is consulted only when requirements are missing or a blocker explicitly requires client action.

## Blocker Policy

- A blocker must use the structured block:

	```
	BLOCKER
	OWNER: ...
	TYPE: tool | permission | dependency | client
	DETAIL: ...
	ASK: ...
	```

- A blocker is terminal only when assessors unanimously return `FINAL_STATUS: BLOCKED`.
- Once blocked, the room stops. Other roles acknowledge the blocker; they do not rephrase it into a new loop.
- Repeating the same blocker under `CONTINUE` is treated as non-productive looping and must be paused by the moderator guard.

## Handoff Contract

- A governed transfer of ownership must use the structured block:

	```
	HANDOFF
	TO: @next_owner
	ROLE: next_role
	ACTION: ...
	STATUS: ...
	```

- Handoffs are emitted as separate room-visible events so the chain is mechanically verifiable.

## Authority Boundaries

- `CLIENT_ESCALATION` is owned only by `delivery_lead`.
- `QUALITY_REJECTED` is owned only by `qa_reviewer`.
- Other roles must classify, recommend, and hand off; they do not bypass these authority boundaries.

## Safe Mode

- `safe_mode` is a governance-proof mode intended to validate command, handoff, and assessment behavior without allowing repository work.
- In `safe_mode`, Northstar may restate the brief, plan, review, hand off, assess, and close the loop textually.
- In `safe_mode`, Northstar must not modify Routify files, run Routify builds/tests, or perform real delivery execution unless explicitly re-enabled in a future client request.
- The current Northstar PASS validates governance in `safe_mode`; it is not the same thing as live autonomous delivery by real LLM workers.

## Autonomy Standard

- There must always be one clear command role.
- There must always be one clear planning owner.
- There must always be one clear execution owner.
- If the current owner is stalled, the lead must redirect ownership or terminate as blocked.
- Silence, ambiguity, and duplicated ownership are governance failures, not acceptable steady state.