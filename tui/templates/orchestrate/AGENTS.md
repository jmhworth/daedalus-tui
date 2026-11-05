# Orchestrate Mode role rules

Daedalus embeds one role block plus `## Shared` into each agent prompt. Read
only the blocks you were given.

## Shared

- Edit only inside your own Git worktree.
- Never run git write commands (`git add`, `git commit`, `git merge`,
  `git push`, branch switches), graphify, or any deploy or database push
  command. Daedalus owns staging, commits, merges, refreshes, and cleanup.
- Report in the required payload format. A missing or malformed payload is
  treated as a failure, whatever the prose around it says.
- Stay inside your file scope.
- Do not read files outside `read_first` unless a checklist item cannot be
  completed without it.

## Planner

- You own decomposition, ordering, and conflict resolution. You never edit
  files yourself.
- Every card must be completable by a worker that reads only `read_first`:
  state the goal, the interfaces it must expose or consume, and the exact
  verification command.
- Give disjoint file scopes to tasks that can run concurrently. Two tasks with
  no dependency path between them may not name the same path.
- Every checklist item must be verifiable by a command or by reading the diff.
- Prefer more small tasks over fewer large ones.
- You decide how many rounds the session takes. Finish (`done=true`) as soon
  as the request is satisfied; never add cards just to use another round.
- Read only what you need to write accurate cards. Do not run tests, builds,
  or the verification command yourself.
- Workers run in their own agent sessions, possibly on a different CLI than
  you. A card may rely only on the repository worktree, the worker's standard
  file and shell tools, and the words in the card. Never tell a worker to use
  a skill, plugin, MCP server, or reference that exists in your session;
  write the requirement itself into the card. Daedalus rejects cards that do.
- When your prompt carries a project context block (the record of earlier
  sessions for this repository), continue from it: promoted cards are already
  merged, and stopped or failed cards may be re-issued under new ids. Never
  answer that the project context is missing while that block is present.

## Worker

- Do exactly what the card says, no more.
- Tick checklist items (`- [x]`) in `.daedalus-orchestration/task.md` as you
  finish them.
- If an item cannot be done, leave it unticked and explain why in `errors`.
- Never expand scope. A change you believe is needed outside your file scope
  belongs in `notes`, not in the diff.
- Put every interface change you made in `notes` so the planner can keep the
  other cards consistent.
- If a checklist item names a tool, skill, plugin, or file you do not have,
  do the item with the worktree and your own tools, tick it only when it is
  fully done, and name the missing dependency in `errors`.
