-- Rex encodes Cmd+Left/Right as Super+arrow (CSI 1;9D / 1;9C). tmux has no
-- Super modifier, folds it into Meta, and forwards Alt+arrow (CSI 1;3D) to the
-- pane, so the shell never sees a line-start/end key. Send Home/End instead,
-- matching the Ghostty keybinds; zsh binds both (beginning/end-of-line).
rex.bind("cmd+left", "pane.send_key", { key = "home" })
rex.bind("cmd+right", "pane.send_key", { key = "end" })

-- Shift+Enter arrives as CSI 27;2;13~, which tmux downgrades to a plain CR, so
-- Claude Code and Codex submit instead of inserting a newline. Send LF (Ctrl+J)
-- for Shift/Opt+Enter, as the Ghostty `text:\x0a` keybinds do.
rex.bind("shift+enter", "pane.send_key", { key = "ctrl+j" })
rex.bind("alt+enter", "pane.send_key", { key = "ctrl+j" })
