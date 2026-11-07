## Chat messages (read only)

```bash
lark-cli im +chat-search --as user --query "群名或成员名"                     # → chat_id oc_…
lark-cli im +chat-messages-list --as user --chat-id oc_… --start 2026-10-17T00:00:00+08:00 \
  --order asc --page-all --no-reactions --concise
lark-cli im +messages-search --as user --query "关键词" [--chat-id oc_…] [--start …]
lark-cli im +threads-messages-list --as user --thread om_…|omt_…
lark-cli im +messages-mget --as user --message-ids om_a,om_b
lark-cli contact +search-user --as user --query "姓名"                       # → open_id ou_…
```

Times are ISO 8601 with offset. Sending messages is outward-facing: only on the user's
explicit request (`lark-cli skills read lark-im` for the send commands).
