## Commands

`scripts/cx` in the skill root (resolve SKILL.md's installed location):

```bash
cx start NAME --effort LEVEL [--ark] [--repo DIR] [--base REF] [--branch BRANCH] < task.md
                               # --ark only when the user asks for Ark; see Lines and effort
cx send NAME < message.md      # follow-up or rework; resumes a closed line first
cx wait NAME [--timeout S]     # until the turn that got the latest message ends; prints the reply
cx diff NAME                   # uncommitted files, commits and diff since the line's base
cx effort NAME LEVEL           # low|medium|high|xhigh, from the next open
cx open NAME                   # resume a closed line without a message
cx attach NAME                 # watch or type in the session (for the user)
cx close NAME [--force]        # end the tmux session; thread, worktree and branch stay
cx ls                          # lines: state, effort, latest message, owner, branch
cx rm NAME [--unmerged|--force]  # when done: remove worktree and line state; branch stays
```

`start` creates the worktree from a fresh `origin/main` by default on branch `codex/NAME`;
pass `--branch` when the repository names branches by convention. Lines live in
`~/.local/share/cx/NAME/` (`msg-NNN.md` sent, `reply-NNN.md` received, `ask-NNN.md` questions,
`wt/` worktree).

After `start` or `send`, run `cx wait` in the background so its completion notifies you, and
keep doing independent work. `send` to a running line steers the message into the current turn
and confirms Codex received it (exit 124 when it cannot; inspect before resending). `wait`
returns only for a turn that received the latest message, so an earlier turn ending never
passes for it. A finished `wait` is the turn's end, not proof the task is done.

