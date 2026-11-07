## Questions from Codex

Codex asks with `cx ask` when a decision is yours. It reaches this session as a cross-session
message starting with `[cx <line>]` that names a question file. Read the file, decide, write
the answer to a scratch file and send it with `cx send <line> < answer.md`; do not answer with
SendMessage, since the sender is a one-shot relay that has already exited.

`cx wait` reports the end of one turn, nothing more; a reply that ends with a question is not
acceptance. After every `cx send`, answers included, start a new background `cx wait`: it binds
to that latest message, while a wait started earlier stays bound to its own message and may
return before the answer's turn ends.

