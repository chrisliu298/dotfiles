-- GitHub Dark colorscheme for Neovim
-- Based on primer/github-vscode-theme, matching Ghostty terminal palette

vim.cmd('highlight clear')
if vim.fn.exists('syntax_on') then vim.cmd('syntax reset') end
vim.g.colors_name = 'github-dark'

-- Palette (from Ghostty GitHub Dark theme)
local c = {
  bg           = '#0d1117',
  fg           = '#e6edf3',
  cursor       = '#2f81f7',
  selection    = '#1b3a5c',
  black        = '#484f58',
  red          = '#ff7b72',
  green        = '#3fb950',
  yellow       = '#d29922',
  blue         = '#58a6ff',
  magenta      = '#bc8cff',
  cyan         = '#39c5cf',
  white        = '#b1bac4',
  bright_black = '#6e7681',
  bright_red   = '#ffa198',
  bright_green = '#56d364',
  bright_yellow = '#e3b341',
  bright_blue  = '#79c0ff',
  bright_magenta = '#d2a8ff',
  bright_cyan  = '#56d4dd',
  bright_white = '#ffffff',
  -- Derived shades
  bg_light     = '#161b22',  -- Slightly lighter bg (UI elements)
  bg_lighter   = '#21262d',  -- Borders, separators
  bg_highlight = '#1c2128',  -- Cursorline, hover
  bg_visual    = '#1b3a5c',  -- Visual selection
  fg_dim       = '#8b949e',  -- Muted text (comments, line numbers)
  fg_dimmer    = '#6e7681',  -- Even more muted
  border       = '#30363d',  -- Window borders, separators
  diff_add_bg  = '#12261e',  -- Diff add background
  diff_del_bg  = '#2d1315',  -- Diff delete background
  diff_chg_bg  = '#272115',  -- Diff change background
}

local function hi(group, opts)
  vim.api.nvim_set_hl(0, group, opts)
end

-- UI
hi('Normal',         { fg = c.fg, bg = c.bg })
hi('NormalFloat',    { fg = c.fg, bg = c.bg_light })
hi('FloatBorder',    { fg = c.border, bg = c.bg_light })
hi('FloatTitle',     { fg = c.blue, bg = c.bg_light, bold = true })
hi('Cursor',         { fg = c.bg, bg = c.cursor })
hi('CursorLine',     { bg = c.bg_highlight })
hi('CursorColumn',   { bg = c.bg_highlight })
hi('ColorColumn',    { bg = c.bg_light })
hi('Visual',         { bg = c.bg_visual })
hi('VisualNOS',      { bg = c.bg_visual })
hi('Search',         { fg = c.bg, bg = c.yellow })
hi('IncSearch',      { fg = c.bg, bg = c.bright_yellow, bold = true })
hi('CurSearch',      { fg = c.bg, bg = c.bright_yellow, bold = true })
hi('Substitute',     { fg = c.bg, bg = c.red })

hi('LineNr',         { fg = c.fg_dimmer })
hi('CursorLineNr',   { fg = c.bright_yellow, bold = true })
hi('SignColumn',     { fg = c.fg_dimmer, bg = c.bg })
hi('FoldColumn',     { fg = c.fg_dimmer, bg = c.bg })
hi('Folded',         { fg = c.fg_dim, bg = c.bg_light })
hi('VertSplit',      { fg = c.border })
hi('WinSeparator',   { fg = c.border })

hi('StatusLine',     { fg = c.fg, bg = c.bg_lighter })
hi('StatusLineNC',   { fg = c.fg_dim, bg = c.bg_light })
hi('TabLine',        { fg = c.fg_dim, bg = c.bg_light })
hi('TabLineSel',     { fg = c.fg, bg = c.bg, bold = true })
hi('TabLineFill',    { bg = c.bg_light })
hi('WinBar',         { fg = c.fg, bg = c.bg, bold = true })
hi('WinBarNC',       { fg = c.fg_dim, bg = c.bg })

hi('Pmenu',          { fg = c.fg, bg = c.bg_light })
hi('PmenuSel',       { fg = c.fg, bg = c.bg_lighter })
hi('PmenuSbar',      { bg = c.bg_lighter })
hi('PmenuThumb',     { bg = c.border })

hi('MatchParen',     { fg = c.bright_yellow, bold = true, underline = true })
hi('NonText',        { fg = c.fg_dimmer })
hi('SpecialKey',     { fg = c.fg_dimmer })
hi('Whitespace',     { fg = c.bg_lighter })
hi('EndOfBuffer',    { fg = c.bg })

hi('Directory',      { fg = c.blue })
hi('Title',          { fg = c.blue, bold = true })
hi('Question',       { fg = c.green })
hi('MoreMsg',        { fg = c.green })
hi('WarningMsg',     { fg = c.yellow })
hi('ErrorMsg',       { fg = c.red, bold = true })
hi('ModeMsg',        { fg = c.fg, bold = true })
hi('MsgArea',        { fg = c.fg })

hi('WildMenu',       { fg = c.bg, bg = c.blue })
hi('QuickFixLine',   { bg = c.bg_visual })

-- Syntax
hi('Comment',        { fg = c.fg_dim, italic = true })
hi('Constant',       { fg = c.bright_blue })
hi('String',         { fg = c.bright_blue })
hi('Character',      { fg = c.bright_blue })
hi('Number',         { fg = c.bright_blue })
hi('Boolean',        { fg = c.bright_blue })
hi('Float',          { fg = c.bright_blue })
hi('Identifier',     { fg = c.fg })
hi('Function',       { fg = c.bright_magenta })
hi('Statement',      { fg = c.red })
hi('Conditional',    { fg = c.red })
hi('Repeat',         { fg = c.red })
hi('Label',          { fg = c.red })
hi('Operator',       { fg = c.red })
hi('Keyword',        { fg = c.red })
hi('Exception',      { fg = c.red })
hi('PreProc',        { fg = c.red })
hi('Include',        { fg = c.red })
hi('Define',         { fg = c.red })
hi('Macro',          { fg = c.bright_blue })
hi('PreCondit',      { fg = c.red })
hi('Type',           { fg = c.red })
hi('StorageClass',   { fg = c.red })
hi('Structure',      { fg = c.red })
hi('Typedef',        { fg = c.red })
hi('Special',        { fg = c.bright_blue })
hi('SpecialChar',    { fg = c.bright_blue })
hi('Tag',            { fg = c.green })
hi('Delimiter',      { fg = c.fg })
hi('SpecialComment', { fg = c.fg_dim, italic = true })
hi('Debug',          { fg = c.red })
hi('Underlined',     { fg = c.blue, underline = true })
hi('Ignore',         { fg = c.fg_dimmer })
hi('Error',          { fg = c.red, bold = true })
hi('Todo',           { fg = c.bright_yellow, bg = c.bg_light, bold = true })
hi('Added',          { fg = c.green })
hi('Changed',        { fg = c.yellow })
hi('Removed',        { fg = c.red })

-- Treesitter
hi('@variable',              { fg = c.fg })
hi('@variable.builtin',      { fg = c.bright_blue })
hi('@variable.parameter',    { fg = c.fg })
hi('@variable.member',       { fg = c.blue })
hi('@constant',              { fg = c.bright_blue })
hi('@constant.builtin',      { fg = c.bright_blue })
hi('@module',                { fg = c.fg })
hi('@string',                { fg = c.bright_blue })
hi('@string.escape',         { fg = c.bright_blue, bold = true })
hi('@string.regex',          { fg = c.bright_blue })
hi('@character',             { fg = c.bright_blue })
hi('@number',                { fg = c.bright_blue })
hi('@boolean',               { fg = c.bright_blue })
hi('@function',              { fg = c.bright_magenta })
hi('@function.builtin',      { fg = c.bright_magenta })
hi('@function.call',         { fg = c.bright_magenta })
hi('@function.method',       { fg = c.bright_magenta })
hi('@function.method.call',  { fg = c.bright_magenta })
hi('@constructor',           { fg = c.bright_magenta })
hi('@keyword',               { fg = c.red })
hi('@keyword.function',      { fg = c.red })
hi('@keyword.return',        { fg = c.red })
hi('@keyword.operator',      { fg = c.red })
hi('@keyword.conditional',   { fg = c.red })
hi('@keyword.repeat',        { fg = c.red })
hi('@keyword.import',        { fg = c.red })
hi('@keyword.exception',     { fg = c.red })
hi('@operator',              { fg = c.red })
hi('@punctuation.bracket',   { fg = c.fg })
hi('@punctuation.delimiter', { fg = c.fg })
hi('@type',                  { fg = c.red })
hi('@type.builtin',          { fg = c.red })
hi('@tag',                   { fg = c.green })
hi('@tag.attribute',         { fg = c.blue })
hi('@tag.delimiter',         { fg = c.fg_dim })
hi('@property',              { fg = c.blue })
hi('@attribute',             { fg = c.blue })
hi('@comment',               { fg = c.fg_dim, italic = true })
hi('@markup.heading',        { fg = c.blue, bold = true })
hi('@markup.link',           { fg = c.blue, underline = true })
hi('@markup.link.url',       { fg = c.blue, underline = true })
hi('@markup.raw',            { fg = c.bright_blue })
hi('@markup.strong',         { bold = true })
hi('@markup.italic',         { italic = true })
hi('@markup.list',           { fg = c.red })

-- Diagnostics
hi('DiagnosticError',          { fg = c.red })
hi('DiagnosticWarn',           { fg = c.yellow })
hi('DiagnosticInfo',           { fg = c.blue })
hi('DiagnosticHint',           { fg = c.cyan })
hi('DiagnosticOk',             { fg = c.green })
hi('DiagnosticUnderlineError', { sp = c.red, underline = true })
hi('DiagnosticUnderlineWarn',  { sp = c.yellow, underline = true })
hi('DiagnosticUnderlineInfo',  { sp = c.blue, underline = true })
hi('DiagnosticUnderlineHint',  { sp = c.cyan, underline = true })
hi('DiagnosticVirtualTextError', { fg = c.red, bg = c.diff_del_bg })
hi('DiagnosticVirtualTextWarn',  { fg = c.yellow, bg = c.diff_chg_bg })
hi('DiagnosticVirtualTextInfo',  { fg = c.blue, bg = c.bg_light })
hi('DiagnosticVirtualTextHint',  { fg = c.cyan, bg = c.bg_light })

-- Diff
hi('DiffAdd',    { bg = c.diff_add_bg })
hi('DiffChange', { bg = c.diff_chg_bg })
hi('DiffDelete', { fg = c.fg_dimmer, bg = c.diff_del_bg })
hi('DiffText',   { bg = '#3b2e10' })

-- Git signs (if added later)
hi('GitSignsAdd',    { fg = c.green })
hi('GitSignsChange', { fg = c.yellow })
hi('GitSignsDelete', { fg = c.red })

-- Spell
hi('SpellBad',  { sp = c.red, undercurl = true })
hi('SpellCap',  { sp = c.yellow, undercurl = true })
hi('SpellRare', { sp = c.magenta, undercurl = true })
hi('SpellLocal', { sp = c.cyan, undercurl = true })

-- LSP (if added later)
hi('LspReferenceText',  { bg = c.bg_lighter })
hi('LspReferenceRead',  { bg = c.bg_lighter })
hi('LspReferenceWrite', { bg = c.bg_lighter, bold = true })
hi('LspSignatureActiveParameter', { fg = c.bright_yellow, bold = true })
