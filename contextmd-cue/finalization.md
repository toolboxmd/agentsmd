---
id: agentsmd-finalization
name: Finalization
applies: The whole task reaches its end: this message requests, approves or reports the merge of this agent's task while its close-out is still due, or the task is stopped, cancelled, superseded or a duplicate, so its Issue, worktrees, branches and processes are to be closed. It continues on later turns (a status ping, a notice about a process it owns, a continue) while that close-out is still open. Not: a pause or sign-off that will resume; ending one part while the task goes on (a superseded review or build, a dev server retired at handoff, a retired host's config); a merge the visible message does not request, approve or report, even if the agent merges later; finishing the handoff or report of a ready PR that still awaits someone's merge, even when the message calls it finalizing; a report that an earlier task's merge and cleanup are already done when the message moves on to new work.
target: ../skills/operations/references/finalization.md
---
AgentsMD: follow the Finalization procedure.
