-- Cache Lua bytecode for faster startup (built-in since 0.9.1)
vim.loader.enable()

-- Set space as the leader key (must be before any leader-based keymaps)
vim.g.mapleader = ' '
vim.g.maplocalleader = ' '

-------------------------------------------------------------------------------
-- Options
-------------------------------------------------------------------------------

-- Display
vim.o.number = true            -- Show absolute line number on the current line
vim.o.relativenumber = true    -- Show relative line numbers for quick j/k jumps
vim.o.mouse = 'a'              -- Enable mouse in all modes (resize splits, scroll, select)
vim.o.showmode = false         -- Don't show -- INSERT -- etc. (redundant with statusline)
vim.o.termguicolors = true     -- Enable 24-bit RGB colors (needed for modern colorschemes)
vim.o.cursorline = true        -- Highlight the line the cursor is on
vim.o.signcolumn = 'yes'       -- Always show sign column (prevents text shifting when signs appear)
vim.o.laststatus = 3           -- Single global statusline instead of one per split

-- Indentation
vim.o.expandtab = true         -- Insert spaces when pressing Tab
vim.o.tabstop = 2              -- Display tab characters as 2 spaces
vim.o.shiftwidth = 2           -- Use 2 spaces for auto-indent (>>, <<, ==)
vim.o.softtabstop = 2          -- Tab/Backspace in insert mode feel like 2 spaces
vim.o.smartindent = true       -- Auto-indent new lines based on syntax (after {, if, etc.)
vim.o.shiftround = true        -- Round indent to nearest multiple of shiftwidth on >> / <<

-- Line wrapping
vim.o.wrap = false             -- Don't visually wrap long lines (scroll horizontally instead)
vim.o.linebreak = true         -- When wrap is on, break at word boundaries, not mid-word
vim.o.breakindent = true       -- Wrapped lines preserve indentation level
vim.o.smoothscroll = true      -- Scroll by screen line when wrapping (0.10+)

-- Search
vim.o.ignorecase = true        -- Case-insensitive search by default
vim.o.smartcase = true         -- ...unless the search pattern contains uppercase letters
vim.o.hlsearch = true          -- Highlight all search matches (clear with <Esc>)

-- Splits
vim.o.splitright = true        -- New vertical splits open to the right
vim.o.splitbelow = true        -- New horizontal splits open below
vim.o.splitkeep = 'screen'     -- Keep text stable on screen when opening/closing splits

-- Scrolling & navigation
vim.o.scrolloff = 10           -- Keep 10 lines visible above/below cursor
vim.o.sidescrolloff = 8        -- Keep 8 columns visible left/right of cursor
vim.o.virtualedit = 'block'    -- Allow cursor past end-of-line in visual block mode
vim.o.inccommand = 'split'     -- Live preview of :s substitutions in a split
vim.o.jumpoptions = 'view'     -- Restore view (scroll position) when jumping back

-- File handling
vim.o.undofile = true          -- Persist undo history across sessions
vim.o.swapfile = false         -- No .swp files (you have undofile + git)
vim.o.backup = false           -- No backup~ files
vim.o.writebackup = false      -- No temporary backup before overwriting
vim.o.autoread = true          -- Auto-reload files changed outside Neovim
vim.o.autowriteall = true      -- Auto-save before :make, :grep, buffer switch, etc.
vim.o.hidden = true            -- Allow switching buffers without saving first
vim.o.confirm = true           -- Prompt to save instead of failing on :q with unsaved changes

-- Timing
vim.o.updatetime = 250         -- Faster CursorHold events (default 4000ms)
vim.o.timeoutlen = 300         -- Time to wait for mapped key sequence (default 1000ms)

-- Whitespace & visual indicators
vim.o.list = true              -- Show invisible characters
vim.opt.listchars = {          -- Which invisible characters to show and how
  tab = '» ',                  --   Tab characters
  trail = '·',                 --   Trailing spaces
  nbsp = '␣',                  --   Non-breaking spaces
  extends = '›',               --   Text continues past right edge (when wrap=false)
  precedes = '‹',              --   Text continues past left edge (when wrap=false)
}
vim.opt.fillchars = {          -- Characters for empty/special areas
  eob = ' ',                   --   Hide ~ tildes on empty lines past end of buffer
  diff = '╱',                  --   Diagonal slash for deleted lines in diff mode
}

-- Completion & command-line
vim.o.pumheight = 10           -- Limit completion popup to 10 entries
vim.o.completeopt = 'menu,menuone,noselect'  -- Show menu even for 1 match, don't auto-select
vim.o.wildmode = 'longest:full,full'  -- First Tab: longest common match + menu; second Tab: cycle
vim.o.wildoptions = 'fuzzy,pum'  -- Fuzzy matching + popup menu for : command completion
vim.opt.wildignore:append({    -- Ignore these patterns in file/command completion
  '.git/*', 'node_modules/*', '__pycache__/*', '*.pyc', '*.o', '*.class',
})
vim.opt.shortmess:append('IcC')  -- I: skip intro screen, c/C: suppress completion messages

-- Folding
vim.o.foldmethod = 'indent'    -- Fold based on indentation level
vim.o.foldlevel = 99           -- Start with all folds open (manually close with zc/zC)

-- Formatting
vim.opt.formatoptions:remove({ 'o', 'r' })  -- Don't auto-insert comment leader on o/O/Enter
vim.opt.formatoptions:append('j')            -- Remove comment leader when joining lines with J

-- Diff
vim.opt.diffopt:append({       -- Better diff display
  'algorithm:histogram',       --   Superior diff algorithm (fewer noisy hunks)
  'linematch:60',              --   Match lines within hunks for clearer diffs (0.11+)
  'indent-heuristic',          --   Smarter hunk boundaries around indentation changes
})

-- File discovery
vim.opt.path:append('**')      -- Make :find search recursively into subdirectories

-- Use ripgrep for :grep (fast project-wide search → quickfix list)
vim.o.grepprg = 'rg --vimgrep --smart-case'
vim.o.grepformat = '%f:%l:%c:%m'

-- Sync clipboard with OS (scheduled to avoid slowing startup)
vim.schedule(function() vim.o.clipboard = 'unnamedplus' end)

-------------------------------------------------------------------------------
-- Netrw (built-in file explorer)
-------------------------------------------------------------------------------

vim.g.netrw_banner = 0         -- Hide the info banner (press I to toggle back)
vim.g.netrw_liststyle = 3      -- Tree-style directory listing

-------------------------------------------------------------------------------
-- Statusline (built-in, no plugin needed)
-------------------------------------------------------------------------------

-- Colorscheme (github-dark matching Ghostty terminal palette, no plugin needed)
vim.cmd.colorscheme('github-dark')

-- %f=filepath %m=modified %r=readonly %==right-align %y=filetype %l=line %c=col %p=percent
vim.o.statusline = ' %f%m%r%= %y  %l:%c  %p%% '

-------------------------------------------------------------------------------
-- Keymaps
-------------------------------------------------------------------------------

-- General
vim.keymap.set('n', '<Esc>', '<cmd>nohlsearch<CR>')      -- Clear search highlights
vim.keymap.set('n', 'Q', '<Nop>')                        -- Disable Ex mode (accidental Q)
vim.keymap.set({ 'n', 'i', 'x', 's' }, '<C-s>', '<cmd>w<CR><Esc>', { desc = 'Save file' })

-- Move by visual/screen lines when no count (so j/k work intuitively on wrapped lines)
vim.keymap.set({ 'n', 'x' }, 'j', "v:count == 0 ? 'gj' : 'j'", { expr = true, silent = true })
vim.keymap.set({ 'n', 'x' }, 'k', "v:count == 0 ? 'gk' : 'k'", { expr = true, silent = true })

-- Center cursor after jumping (keeps your eyes in one place)
vim.keymap.set('n', '<C-d>', '<C-d>zz')                  -- Half-page down + center
vim.keymap.set('n', '<C-u>', '<C-u>zz')                  -- Half-page up + center
vim.keymap.set('n', 'n', 'nzzzv')                        -- Next search match + center + open fold
vim.keymap.set('n', 'N', 'Nzzzv')                        -- Prev search match + center + open fold
vim.keymap.set('n', '*', '*zzzv')                        -- Search word forward + center + open fold
vim.keymap.set('n', '#', '#zzzv')                        -- Search word backward + center + open fold

-- Line manipulation
vim.keymap.set('n', 'J', 'mzJ`z', { desc = 'Join lines (cursor stays)' })  -- Join without cursor jumping
vim.keymap.set('v', 'J', ":m '>+1<CR>gv=gv", { silent = true, desc = 'Move selection down' })  -- Move selected lines down
vim.keymap.set('v', 'K', ":m '<-2<CR>gv=gv", { silent = true, desc = 'Move selection up' })    -- Move selected lines up
vim.keymap.set('v', '<', '<gv')                          -- Indent left and keep selection
vim.keymap.set('v', '>', '>gv')                          -- Indent right and keep selection

-- Register-safe operations
vim.keymap.set('x', '<leader>p', '"_dP', { desc = 'Paste without overwriting register' })  -- Paste over selection without losing yanked text
vim.keymap.set({ 'n', 'x' }, 'x', '"_x', { desc = 'Delete char (no register)' })           -- Delete char without polluting clipboard

-- Buffer navigation
vim.keymap.set('n', '<S-h>', '<cmd>bprevious<CR>', { silent = true, desc = 'Previous buffer' })
vim.keymap.set('n', '<S-l>', '<cmd>bnext<CR>', { silent = true, desc = 'Next buffer' })
vim.keymap.set('n', '<leader><tab>', '<C-^>', { desc = 'Alternate buffer' })  -- Toggle between last two buffers

-- Quickfix & location list navigation
vim.keymap.set('n', ']q', '<cmd>cnext<CR>zz', { silent = true, desc = 'Next quickfix' })
vim.keymap.set('n', '[q', '<cmd>cprev<CR>zz', { silent = true, desc = 'Prev quickfix' })
vim.keymap.set('n', ']l', '<cmd>lnext<CR>zz', { silent = true, desc = 'Next loclist' })
vim.keymap.set('n', '[l', '<cmd>lprev<CR>zz', { silent = true, desc = 'Prev loclist' })

-- Insert blank lines without entering insert mode
vim.keymap.set('n', ']<space>', 'o<Esc>k', { desc = 'Add blank line below' })
vim.keymap.set('n', '[<space>', 'O<Esc>j', { desc = 'Add blank line above' })

-- Utilities
vim.keymap.set('n', '<leader>sr', [[:%s/\<<C-r><C-w>\>/<C-r><C-w>/gcI<Left><Left><Left><Left>]], { desc = 'Search and replace word' })  -- Pre-fill :%s with word under cursor
vim.keymap.set('n', '<leader>e', '<cmd>Lexplore<CR>', { desc = 'Toggle file explorer' })  -- Toggle netrw sidebar
vim.keymap.set('n', '<leader>ts', '<cmd>set spell!<CR>', { desc = 'Toggle spell check' })

-- Window resize with arrow keys
vim.keymap.set('n', '<C-Up>', '<cmd>resize +2<CR>', { desc = 'Increase window height' })
vim.keymap.set('n', '<C-Down>', '<cmd>resize -2<CR>', { desc = 'Decrease window height' })
vim.keymap.set('n', '<C-Left>', '<cmd>vertical resize -2<CR>', { desc = 'Decrease window width' })
vim.keymap.set('n', '<C-Right>', '<cmd>vertical resize +2<CR>', { desc = 'Increase window width' })

-- Window navigation with Ctrl+hjkl
vim.keymap.set('n', '<C-h>', '<C-w><C-h>', { desc = 'Move focus to the left window' })
vim.keymap.set('n', '<C-l>', '<C-w><C-l>', { desc = 'Move focus to the right window' })
vim.keymap.set('n', '<C-j>', '<C-w><C-j>', { desc = 'Move focus to the lower window' })
vim.keymap.set('n', '<C-k>', '<C-w><C-k>', { desc = 'Move focus to the upper window' })

-- Terminal keymaps
vim.keymap.set('t', '<Esc><Esc>', '<C-\\><C-n>', { desc = 'Exit terminal mode' })  -- Double-Esc exits terminal mode
vim.keymap.set('t', '<C-h>', '<C-\\><C-n><C-w>h')  -- Window nav works from terminal too
vim.keymap.set('t', '<C-j>', '<C-\\><C-n><C-w>j')
vim.keymap.set('t', '<C-k>', '<C-\\><C-n><C-w>k')
vim.keymap.set('t', '<C-l>', '<C-\\><C-n><C-w>l')

-------------------------------------------------------------------------------
-- Autocommands
-------------------------------------------------------------------------------

-- Briefly highlight yanked text for visual feedback
vim.api.nvim_create_autocmd('TextYankPost', {
  group = vim.api.nvim_create_augroup('highlight-yank', { clear = true }),
  callback = function() vim.hl.on_yank() end,
})

-- Restore cursor to last position when reopening a file (skip git commits)
vim.api.nvim_create_autocmd('BufReadPost', {
  group = vim.api.nvim_create_augroup('restore-cursor', { clear = true }),
  callback = function(args)
    if vim.bo[args.buf].filetype == 'gitcommit' then return end
    local mark = vim.api.nvim_buf_get_mark(args.buf, '"')
    local lcount = vim.api.nvim_buf_line_count(args.buf)
    if mark[1] > 0 and mark[1] <= lcount then
      pcall(vim.api.nvim_win_set_cursor, 0, mark)
    end
  end,
})

-- Auto-rebalance splits when terminal window is resized
vim.api.nvim_create_autocmd('VimResized', {
  group = vim.api.nvim_create_augroup('resize-splits', { clear = true }),
  callback = function()
    local current_tab = vim.fn.tabpagenr()
    vim.cmd('tabdo wincmd =')
    vim.cmd('tabnext ' .. current_tab)
  end,
})

-- Auto-create missing parent directories when saving a new file
vim.api.nvim_create_autocmd('BufWritePre', {
  group = vim.api.nvim_create_augroup('auto-mkdir', { clear = true }),
  callback = function(args)
    if args.match:match('^%w%w+:[\\/][\\/]') then return end  -- Skip URLs (e.g., scp://)
    local file = vim.uv.fs_realpath(args.match) or args.match
    vim.fn.mkdir(vim.fn.fnamemodify(file, ':p:h'), 'p')
  end,
})

-- Strip trailing whitespace on save (preserves cursor position)
vim.api.nvim_create_autocmd('BufWritePre', {
  group = vim.api.nvim_create_augroup('trim-whitespace', { clear = true }),
  callback = function()
    local view = vim.fn.winsaveview()
    vim.cmd([[%s/\s\+$//e]])
    vim.fn.winrestview(view)
  end,
})

-- Reload file if it was changed externally (git checkout, formatter, etc.)
vim.api.nvim_create_autocmd({ 'FocusGained', 'TermClose', 'TermLeave' }, {
  group = vim.api.nvim_create_augroup('checktime', { clear = true }),
  callback = function()
    if vim.o.buftype ~= 'nofile' then vim.cmd('checktime') end
  end,
})

-- Close transient buffers (help, quickfix, etc.) with just q
vim.api.nvim_create_autocmd('FileType', {
  group = vim.api.nvim_create_augroup('close-with-q', { clear = true }),
  pattern = { 'help', 'lspinfo', 'man', 'qf', 'checkhealth', 'startuptime' },
  callback = function(args)
    vim.bo[args.buf].buflisted = false
    vim.keymap.set('n', 'q', '<cmd>close<CR>', { buffer = args.buf, silent = true })
  end,
})

-- Enable word wrap and spell check for prose filetypes
vim.api.nvim_create_autocmd('FileType', {
  group = vim.api.nvim_create_augroup('wrap-spell', { clear = true }),
  pattern = { 'markdown', 'text', 'gitcommit', 'tex' },
  callback = function()
    vim.opt_local.wrap = true
    vim.opt_local.spell = true
  end,
})

-- Clean up terminal buffers: no line numbers, no sign column, start in insert mode
vim.api.nvim_create_autocmd('TermOpen', {
  group = vim.api.nvim_create_augroup('terminal-setup', { clear = true }),
  callback = function()
    vim.opt_local.number = false
    vim.opt_local.relativenumber = false
    vim.opt_local.signcolumn = 'no'
    vim.cmd.startinsert()
  end,
})

-- Auto-open quickfix window after :grep, :make, etc.
vim.api.nvim_create_autocmd('QuickFixCmdPost', {
  group = vim.api.nvim_create_augroup('quickfix-auto-open', { clear = true }),
  pattern = { '[^l]*' },
  command = 'cwindow',
})

-- vim: ts=2 sts=2 sw=2 et
