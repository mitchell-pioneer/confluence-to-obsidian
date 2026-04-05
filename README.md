# Confluence to Obsidian Converter

Converts Confluence HTML space exports to clean Obsidian-compatible Markdown.

## Features

- Preserves page hierarchy from breadcrumbs as folder structure
- Converts internal links to Obsidian `[[wiki links]]`
- Converts images to Obsidian `![[embed]]` format
- Auto-detects code block languages (bash, json, yaml, etc.)
- Escapes `$$` to prevent LaTeX math mode conflicts
- Removes Confluence navigation chrome, scripts, and metadata
- Sanitizes filenames for Windows compatibility
- Unwraps link-protection URLs

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

## Obsidian Tips

Add this CSS snippet (Settings > Appearance > CSS Snippets) to prevent code block wrapping:

```css
.markdown-rendered pre code { white-space: pre; overflow-wrap: normal; }
.markdown-rendered pre { overflow-x: auto; }
```
