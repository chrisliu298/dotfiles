## Questions from Codex

Codex asks with `agent-msg send` when a decision is yours. The question reaches this session as
`[peer] agent-msg read ID`: run that command; its `sender_name` is `cx-<line>`. Decide, write the
answer to a scratch file and send it with `cx send <line> < answer.md`. The line is a send-only
peer, so `agent-msg reply` to it is refused. This works only when this session is registered with
agent-msg (`agent-msg whoami`); otherwise questions arrive in the line's replies.

`cx wait` reports the end of one turn, nothing more; a reply that ends with a question is not
acceptance. After every `cx send`, answers included, start a new background `cx wait`: it binds
to that latest message, while a wait started earlier stays bound to its own message and may
return before the answer's turn ends.
