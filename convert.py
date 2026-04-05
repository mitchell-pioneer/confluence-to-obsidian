#!/usr/bin/env python3
"""Confluence HTML Export to Obsidian Markdown Converter.

Converts Confluence HTML space exports to clean Obsidian-compatible Markdown,
preserving page hierarchy, wiki links, images, and code blocks.

Requirements:
    - Python 3.10+
    - pandoc (https://pandoc.org/installing.html)
    - beautifulsoup4 (auto-installed if missing)

Usage:
    python convert.py <source_dir> <dest_dir>
    python convert.py ./EI ~/MyVault/confluence-import
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    print("Installing beautifulsoup4...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4"])
    from bs4 import BeautifulSoup, NavigableString, Tag

MAX_FILENAME_LEN = 150

LANG_MAP = {
    'python': 'python', 'py': 'python', 'javascript': 'javascript',
    'js': 'javascript', 'bash': 'bash', 'shell': 'bash', 'sh': 'bash',
    'sql': 'sql', 'xml': 'xml', 'html': 'html', 'css': 'css', 'json': 'json',
    'yaml': 'yaml', 'yml': 'yaml', 'ruby': 'ruby', 'php': 'php', 'c': 'c',
    'cpp': 'cpp', 'csharp': 'csharp', 'go': 'go', 'rust': 'rust',
    'powershell': 'powershell', 'ps': 'powershell', 'text': 'text', 'plain': 'text',
    'groovy': 'groovy', 'scala': 'scala', 'swift': 'swift', 'kotlin': 'kotlin',
    'typescript': 'typescript', 'ts': 'typescript', 'dockerfile': 'dockerfile',
    'nginx': 'nginx', 'apache': 'apache', 'ini': 'ini', 'toml': 'toml',
}

SHELL_INDICATORS = [
    'sudo ', 'apt-get ', 'apt ', 'pip ', 'npm ', 'yarn ', 'docker ', 'git ',
    'cd ', 'ls ', 'mkdir ', 'cp ', 'mv ', 'rm ', 'chmod ', 'chown ', 'cat ',
    'echo ', 'export ', 'source ', 'curl ', 'wget ', 'ssh ', 'scp ', 'rsync ',
    'systemctl ', 'service ', 'nano ', 'vim ', 'aws ', 'kubectl ', 'helm ',
    'terraform ', 'ansible ', 'vagrant ', 'make ', 'cmake ', 'python3 ',
    'python ', 'pip3 ', 'brew ', 'yum ', 'dnf ', 'pacman ', 'snap ',
    'msiexec', 'choco ', 'winget ', 'ifconfig', 'ip addr', 'ping ',
    'netstat', 'ss -', 'journalctl', 'grep ', 'awk ', 'sed ', 'find ',
    '#!/bin/', 'set -', '$ ', '# ',
]


def guess_code_language(code_text: str) -> str:
    text = code_text.strip()
    first_line = text.split('\n')[0].strip().lower()
    for indicator in SHELL_INDICATORS:
        if first_line.startswith(indicator.lower()) or any(
            line.strip().lower().startswith(indicator.lower())
            for line in text.split('\n')[:5]
        ):
            return 'bash'
    if text.startswith('{') and text.rstrip().endswith('}'):
        return 'json'
    if text.startswith('[') and text.rstrip().endswith(']'):
        return 'json'
    if re.match(r'^[a-zA-Z_]+:\s', first_line) and '---' in text[:20]:
        return 'yaml'
    if text.startswith('http://') or text.startswith('https://'):
        return ''
    if any(c in text for c in ['┌', '│', '└', '├', '═', '╔']):
        return ''
    if re.search(r'^(import |package |public |private |class )', text, re.MULTILINE):
        return 'java'
    return ''


def sanitize_filename(name: str) -> str:
    clean = re.sub(r'[\\/:*?"<>|~#%&{}!$@`+\[\]]', '_', name)
    clean = re.sub(r'_{2,}', '_', clean)
    clean = clean.strip('_ .')
    if len(clean) > MAX_FILENAME_LEN:
        clean = clean[:MAX_FILENAME_LEN]
    return clean


def extract_title(soup: BeautifulSoup) -> str | None:
    title_span = soup.find('span', id='title-text')
    if title_span:
        text = title_span.get_text(strip=True)
        if ' : ' in text:
            text = text.split(' : ', 1)[1]
        return text
    title_tag = soup.find('title')
    if title_tag:
        text = title_tag.get_text(strip=True)
        if ' : ' in text:
            text = text.split(' : ', 1)[1]
        return text
    return None


def extract_breadcrumb_path(soup: BeautifulSoup) -> str:
    bc = soup.find('div', id='breadcrumb-section')
    if not bc:
        return ''
    crumbs = [a.get_text(strip=True) for a in bc.find_all('a')]
    if crumbs:
        crumbs = crumbs[1:]  # Remove root space name
    crumbs = [sanitize_filename(c) for c in crumbs if c]
    return os.path.join(*crumbs) if crumbs else ''


def extract_content(soup: BeautifulSoup) -> Tag | None:
    main_content = soup.find('div', id='main-content')
    if not main_content:
        main_content = soup.find('div', id='content')
    if not main_content:
        return None
    for tag in main_content.find_all('script'):
        tag.decompose()
    for tag in main_content.find_all('style'):
        tag.decompose()
    for tag in main_content.find_all('div', class_='page-metadata'):
        tag.decompose()
    for tag in main_content.find_all('div', class_='pageSection'):
        tag.decompose()
    for table in main_content.find_all('table', class_='attachments'):
        table.decompose()
    for tag in main_content.find_all('div', class_='ap-container'):
        tag.decompose()
    return main_content


def simplify_images(content: Tag) -> None:
    for img in content.find_all('img'):
        src = img.get('src', '')
        if not src:
            img.decompose()
            continue
        src = src.split('?')[0]
        if src.startswith('images/icons/') or 'thumbnails' in src:
            img.decompose()
            continue
        img.attrs = {'src': src, 'alt': img.get('alt', '')}


def simplify_links(content: Tag, html_to_title: dict) -> None:
    for a in list(content.find_all('a')):
        href = a.get('href', '')
        text = a.get_text(strip=True)
        if not href or href == '#':
            a.replace_with(text if text else '')
            continue
        if href.endswith('.html') and not href.startswith(('http://', 'https://')):
            filename = os.path.basename(href)
            if filename in html_to_title:
                a.replace_with(f'[[{html_to_title[filename]}|{text}]]')
            else:
                a.replace_with(text if text else '')
            continue
        a.attrs = {'href': href}
        if not text:
            a.string = href


def simplify_code_blocks(content: Tag, soup: BeautifulSoup) -> None:
    for pre in content.find_all('pre', class_='syntaxhighlighter-pre'):
        params = pre.get('data-syntaxhighlighter-params', '')
        lang = ''
        brush_match = re.search(r'brush:\s*(\w+)', params)
        if brush_match:
            brush = brush_match.group(1).lower()
            if brush == 'java':
                lang = guess_code_language(pre.get_text())
            else:
                lang = LANG_MAP.get(brush, brush)
        code_text = pre.get_text()
        new_pre = soup.new_tag('pre')
        new_code = soup.new_tag('code')
        new_code['class'] = [f'language-{lang}'] if lang else ['language-text']
        new_code.string = code_text
        new_pre.append(new_code)
        panel = pre.find_parent('div', class_='code')
        if panel:
            panel.replace_with(new_pre)
        else:
            pre.replace_with(new_pre)


def remove_confluence_macros(content: Tag) -> None:
    for macro in content.find_all('div', class_=re.compile(r'confluence-information-macro')):
        body = macro.find('div', class_='confluence-information-macro-body')
        if body:
            macro.replace_with(body)
        else:
            macro.decompose()
    for expand in content.find_all('div', class_='expand-container'):
        content_el = expand.find('div', class_='expand-content')
        if content_el:
            expand.replace_with(content_el)
    for div in content.find_all('div', class_=re.compile(r'^(panel|panelContent|codeContent|contentLayout|columnLayout|cell)')):
        div.unwrap()


def strip_all_attributes(content: Tag) -> None:
    KEEP_CLASSES = {'language-'}
    for tag in content.find_all(True):
        if tag.name in ('pre', 'code'):
            cls = tag.get('class', [])
            lang_classes = [c for c in cls if any(c.startswith(k) for k in KEEP_CLASSES)]
            tag.attrs = {}
            if lang_classes:
                tag['class'] = lang_classes
        elif tag.name == 'a':
            href = tag.get('href', '')
            tag.attrs = {'href': href} if href else {}
        elif tag.name == 'img':
            src = tag.get('src', '')
            alt = tag.get('alt', '')
            tag.attrs = {'src': src}
            if alt:
                tag['alt'] = alt
        elif tag.name in ('td', 'th'):
            cs = tag.get('colspan')
            rs = tag.get('rowspan')
            tag.attrs = {}
            if cs: tag['colspan'] = cs
            if rs: tag['rowspan'] = rs
        else:
            tag.attrs = {}


def convert_html_to_markdown(html_content: str) -> str:
    try:
        result = subprocess.run(
            ['pandoc', '-f', 'html', '-t', 'gfm', '--wrap=none', '--strip-comments'],
            input=html_content, capture_output=True, text=True, encoding='utf-8', timeout=30
        )
        if result.returncode == 0:
            return result.stdout
    except (subprocess.TimeoutExpired, Exception) as e:
        print(f"  Pandoc error: {e}")
    return ""


def clean_markdown(md: str) -> str:
    # Remove remaining HTML tags
    for tag in ['div', 'span', 'colgroup', 'tbody', 'thead']:
        md = re.sub(rf'</?{tag}[^>]*>', '', md)
    md = re.sub(r'</?col[^>]*/?>', '', md)
    md = re.sub(r'</?u>', '', md)

    # Remove pandoc attribute blocks
    md = re.sub(r'\{#[^}]+\}', '', md)
    md = re.sub(r'\{\.[\w-][^}]*\}', '', md)
    md = re.sub(r'\{[^}]*="[^"]*"[^}]*\}', '', md)
    md = re.sub(r'\{\s*\}', '', md)

    # Fix wiki links escaped by pandoc
    md = re.sub(r'\\\[\\\[', '[[', md)
    md = re.sub(r'\\\]\\\]', ']]', md)
    md = re.sub(r'\\\[{2}', '[[', md)
    md = re.sub(r'\\\]{2}', ']]', md)
    md = re.sub(r'\[\[([^\]]+?)\\\|([^\]]+?)\]\]', r'[[\1|\2]]', md)

    # Images to Obsidian embeds
    md = re.sub(r'!\[([^\]]*)\]\((attachments/[^)]+)\)', r'![[\2]]', md)

    md = re.sub(r'``` syntaxhighlighter-pre', '```', md)

    # Unwrap linkprotect URLs
    md = re.sub(
        r'\[([^\]]+)\]\(https://linkprotect\.cudasvc\.com/url\?a=([^&]+)&[^)]*\)',
        lambda m: f'[{m.group(1)}]({m.group(2).replace("%3a", ":").replace("%2f", "/").replace("%3A", ":").replace("%2F", "/")})',
        md
    )
    md = re.sub(
        r'<https://linkprotect\.cudasvc\.com/url\?a=([^&]+)&[^>]*>',
        lambda m: m.group(1).replace('%3a', ':').replace('%2f', '/').replace('%3A', ':').replace('%2F', '/'),
        md
    )

    # Remove Confluence upload remnants
    for pattern in [r'^Drag and drop to upload or browse for files\s*$', r'^Upload file\s*$',
                    r'^File description\s*$', r'^\[Download All\]\([^)]*\)\s*$']:
        md = re.sub(f'(?m){pattern}', '', md)

    # Clean user profile links
    md = re.sub(r'\[([^\]]+)\]\(/wiki/display/~[^)]+\)', r'\1', md)
    md = re.sub(r'\[([^\]]+)\]\(/wiki/people/[^)]+\)', r'\1', md)

    # Convert remaining raw <a> tags
    md = re.sub(r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>', lambda m: f'[{m.group(2)}]({m.group(1)})', md)

    md = md.replace('&#10;', '')

    # Escape $$ outside code blocks to prevent LaTeX math mode
    lines = md.split('\n')
    in_code = False
    for i, line in enumerate(lines):
        if line.strip().startswith('```'):
            in_code = not in_code
        elif not in_code and '$$' in line:
            lines[i] = line.replace('$$', r'\$\$')
    md = '\n'.join(lines)

    # Collapse loose lists
    for pattern in [r'(\n\d+\.\s{1,3}[^\n]+)\n\n(\d+\.\s)', r'(\n[-*]\s+[^\n]+)\n\n([-*]\s)',
                    r'(\n\s+\d+\.\s{1,3}[^\n]+)\n\n(\s+\d+\.\s)', r'(\n\s+[-*]\s+[^\n]+)\n\n(\s+[-*]\s)']:
        for _ in range(20):
            new_md = re.sub(pattern, r'\1\n\2', md)
            if new_md == md: break
            md = new_md

    # Convert 4-space indented code blocks to fenced
    result_lines = []
    lines = md.split('\n')
    i = 0
    while i < len(lines):
        if (lines[i].startswith('    ')
                and not lines[i].strip().startswith(('-', '*', '!'))
                and not re.match(r'\s*\d+\.', lines[i].strip())
                and (i == 0 or lines[i-1].strip() == '')):
            block = []
            while i < len(lines):
                if lines[i].startswith('    '):
                    block.append(lines[i][4:])
                    i += 1
                elif lines[i].strip() == '' and i + 1 < len(lines) and lines[i+1].startswith('    '):
                    block.append('')
                    i += 1
                else:
                    break
            if any(l.strip() for l in block):
                result_lines.append('```')
                result_lines.extend(block)
                result_lines.append('```')
            else:
                result_lines.extend(['    ' + l for l in block])
        else:
            result_lines.append(lines[i])
            i += 1
    md = '\n'.join(result_lines)

    md = re.sub(r'(?m)^(\s*\d+\.)\s{2,}', r'\1 ', md)
    md = re.sub(r'\n{3,}', '\n\n', md)
    md = re.sub(r'(?m)^\s+$', '', md)
    md = re.sub(r'(?m) +$', '', md)
    return md.strip()


def build_title_map(source_dir: Path) -> dict:
    title_map = {}
    for html_file in source_dir.glob('*.html'):
        try:
            with open(html_file, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(2000)
            soup = BeautifulSoup(content, 'html.parser')
            title = extract_title(soup)
            if title:
                title_map[html_file.name] = title
        except Exception:
            pass
    return title_map


def main():
    parser = argparse.ArgumentParser(
        description='Convert Confluence HTML export to Obsidian Markdown'
    )
    parser.add_argument('source', help='Path to extracted Confluence HTML export directory')
    parser.add_argument('dest', help='Destination directory for Obsidian Markdown files')
    args = parser.parse_args()

    source_dir = Path(args.source).resolve()
    dest_dir = Path(args.dest).resolve()

    print("\n============================================")
    print(" Confluence to Obsidian Converter")
    print("============================================\n")

    try:
        subprocess.run(['pandoc', '--version'], capture_output=True, check=True)
        print("[OK] Pandoc found")
    except Exception:
        print("ERROR: Pandoc is not installed or not in PATH.")
        print()
        if sys.platform == 'win32':
            answer = input("Install pandoc via chocolatey? (y/n): ").strip().lower()
            if answer == 'y':
                print("Installing pandoc...")
                subprocess.run(['choco', 'install', 'pandoc', '-y'], check=True)
                print("[OK] Pandoc installed. You may need to restart your terminal.")
            else:
                print("Please install pandoc: https://pandoc.org/installing.html")
        else:
            print("Install with: sudo apt install pandoc  (or brew install pandoc)")
        return

    if not source_dir.exists():
        print(f"ERROR: Source not found: {source_dir}")
        return

    if dest_dir.exists():
        print("Cleaning previous conversion...")
        shutil.rmtree(dest_dir, ignore_errors=True)
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"[OK] Source: {source_dir}")
    print(f"[OK] Destination: {dest_dir}")

    html_files = list(source_dir.glob('*.html'))
    print(f"\nFound {len(html_files)} HTML files to convert.\n")

    print("Building title map for wiki links...")
    title_map = build_title_map(source_dir)
    print(f"[OK] Mapped {len(title_map)} page titles.\n")

    print("Copying attachments...")
    att_count = 0
    att_source = source_dir / 'attachments'
    if att_source.exists():
        att_dest = dest_dir / 'attachments'
        shutil.copytree(att_source, att_dest, dirs_exist_ok=True)
        att_count = sum(1 for _ in att_dest.rglob('*') if _.is_file())
    print(f"[OK] Copied {att_count} attachment files.\n")

    print("Converting HTML to Markdown...\n")
    converted = 0
    skipped = 0
    errors = []
    used_names = set()

    for i, html_file in enumerate(sorted(html_files), 1):
        try:
            with open(html_file, 'r', encoding='utf-8', errors='replace') as f:
                raw_html = f.read()

            soup = BeautifulSoup(raw_html, 'html.parser')
            title = extract_title(soup)
            if not title:
                title = html_file.stem

            folder_path = extract_breadcrumb_path(soup)

            content = extract_content(soup)
            if content is None:
                print(f"  [{i}/{len(html_files)}] SKIP (no content): {html_file.name}")
                skipped += 1
                continue

            text_content = content.get_text(strip=True)
            if len(text_content) < 5 and not content.find_all('img'):
                print(f"  [{i}/{len(html_files)}] SKIP (empty): {title}")
                skipped += 1
                continue

            simplify_code_blocks(content, soup)
            simplify_images(content)
            simplify_links(content, title_map)
            remove_confluence_macros(content)
            strip_all_attributes(content)

            clean_html = f'<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>{content}</body></html>'
            md = convert_html_to_markdown(clean_html)
            if not md.strip():
                print(f"  [{i}/{len(html_files)}] SKIP (empty conversion): {title}")
                skipped += 1
                continue

            md = clean_markdown(md)

            safe_name = sanitize_filename(title)
            if not safe_name:
                safe_name = sanitize_filename(html_file.stem)

            out_dir = (dest_dir / folder_path) if folder_path else dest_dir
            out_dir.mkdir(parents=True, exist_ok=True)

            full_key = f"{folder_path}/{safe_name}".lower()
            base_name = safe_name
            counter = 2
            while full_key in used_names:
                safe_name = f"{base_name}_{counter}"
                full_key = f"{folder_path}/{safe_name}".lower()
                counter += 1
            used_names.add(full_key)

            depth = len(Path(folder_path).parts) if folder_path else 0
            if depth > 0:
                prefix = '/'.join(['..'] * depth)
                md = md.replace('![[attachments/', f'![[{prefix}/attachments/')
                md = re.sub(r'\[([^\]]*)\]\(attachments/', rf'[\1]({prefix}/attachments/', md)

            out_file = out_dir / f"{safe_name}.md"
            with open(out_file, 'w', encoding='utf-8', newline='\n') as f:
                f.write(md)

            converted += 1
            rel_path = f"{folder_path}/{safe_name}.md" if folder_path else f"{safe_name}.md"
            print(f"  [{i}/{len(html_files)}] OK: {rel_path}")

        except Exception as e:
            print(f"  [{i}/{len(html_files)}] ERROR: {html_file.name} - {e}")
            errors.append((html_file.name, str(e)))

    print(f"\n============================================")
    print(f" Conversion Complete")
    print(f"============================================\n")
    print(f"  Total:     {len(html_files)}")
    print(f"  Converted: {converted}")
    print(f"  Skipped:   {skipped}")
    print(f"  Errors:    {len(errors)}")
    print(f"\n  Output: {dest_dir}\n")

    if errors:
        print("Files with errors:")
        for name, err in errors:
            print(f"  - {name}: {err}")


if __name__ == '__main__':
    main()
