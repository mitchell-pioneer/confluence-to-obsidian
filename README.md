# Confluence to Obsidian Converter

Converts Confluence HTML space exports to clean Obsidian-compatible Markdown.

**This tool was fully written by Claude (Anthropic) via Claude Code.**

## Why This Exists

The Confluence HTML export dumps all pages into a single flat folder with numeric filenames, and existing import tools (including Obsidian's community plugins) crash on many exports due to illegal characters, malformed links, and unhandled edge cases. This converter was built to handle real-world Confluence exports reliably on Windows.

## Windows-Specific Bugs Fixed

- **Illegal filename characters**: Confluence page titles often contain `*`, `?`, `<`, `>`, `|`, `:`, etc. which are illegal in Windows filenames. All are sanitized to `_`.
- **Path length limit**: Windows has a 260-character path limit. Long titles are truncated to stay under the limit.
- **`$$` triggers LaTeX math mode**: Confluence pages with passwords like `Pioneer$$8900` cause Obsidian to enter LaTeX rendering mode, breaking all formatting after that point. All `$$` outside code blocks are escaped to `\$\$`.
- **CRLF line ending issues**: Mixed or Windows-style line endings can cause Obsidian to fail to recognize fenced code blocks. Output uses consistent LF-only line endings.
- **Pandoc auto-install prompt**: If pandoc is not found, prompts to install via Chocolatey on Windows.

## Features

- Preserves page hierarchy from breadcrumbs as folder structure (not flat!)
- Converts internal links to Obsidian `[[wiki links]]`
- Converts images to Obsidian `![[embed]]` format with correct relative paths
- Auto-detects code block languages (bash, json, yaml, etc.) instead of Confluence's default "java" for everything
- Forces fenced code blocks (pandoc sometimes generates indented blocks that render poorly)
- Removes Confluence navigation chrome, scripts, metadata, and attachment tables
- Unwraps linkprotect.cudasvc.com redirect URLs to the actual destination
- Collapses loose lists (removes excess blank lines between list items)
- Sanitizes filenames and handles duplicates

## Prerequisites

- Python 3.10+
- [Pandoc](https://pandoc.org/installing.html)
- beautifulsoup4 (auto-installed on first run)

## Usage

1. Export your Confluence space as HTML (Space Settings > Export)
2. Extract the zip file
3. Run the converter:

```bash
python convert.py <extracted_folder> <obsidian_vault_folder>
```

Example:
```bash
python convert.py ./EI ~/MyVault/confluence-import
```

## Recommended Obsidian Plugins

- **Code Styler** - Adds line numbers, syntax highlighting themes, and no-wrap scrolling to code blocks, matching the Confluence code block appearance. Install from Settings > Community Plugins > Browse > search "Code Styler".
