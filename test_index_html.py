"""Verification test for index.html (and saathi_ai_trained.html).

Extracts every <script> block from index.html and:
1. Runs `node --check` on each extracted script block to verify JS syntax.
2. Extracts all DOM element IDs referenced in JS (e.g. $('id'), getElementById('id'), querySelector('#id'))
   and verifies that every referenced ID exists in the HTML.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent
HTML_FILES = ["index.html", "saathi_ai_trained.html"]


def extract_script_blocks(html_content: str) -> list[str]:
    """Extract inline JavaScript code from <script> tags, ignoring external or non-JS scripts."""
    # Pattern to match <script>...</script>
    pattern = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.DOTALL | re.IGNORECASE)
    scripts = []
    for attrs, body in pattern.findall(html_content):
        # Ignore external scripts like <script src="...">
        if re.search(r'\bsrc\s*=', attrs, re.I):
            continue
        # Ignore json/ld or template scripts
        type_match = re.search(r'\btype\s*=\s*["\']([^"\']+)["\']', attrs, re.I)
        if type_match:
            t = type_match.group(1).lower().strip()
            if t not in {"text/javascript", "application/javascript", "module", ""}:
                continue
        code = body.strip()
        if code:
            scripts.append(code)
    return scripts


def extract_html_ids(html_content: str) -> set[str]:
    """Extract all element IDs defined in the HTML markup outside script tags."""
    # Strip script and style blocks first
    clean_html = re.sub(r"<script\b[^>]*>.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
    clean_html = re.sub(r"<style\b[^>]*>.*?</style>", "", clean_html, flags=re.DOTALL | re.IGNORECASE)
    
    # Match id="..." or id='...'
    matches = re.findall(r'''\bid\s*=\s*["']([^"']+)["']''', clean_html)
    return set(matches)


def extract_js_referenced_ids(js_code: str) -> set[str]:
    """Extract all DOM IDs referenced in JavaScript code."""
    referenced = set()
    
    # 1. $('id') or $("id")
    for m in re.findall(r'''\$\(\s*["']([a-zA-Z0-9_\-]+)["']\s*\)''', js_code):
        referenced.add(m)
        
    # 2. document.getElementById('id') or getElementById("id")
    for m in re.findall(r'''getElementById\(\s*["']([a-zA-Z0-9_\-]+)["']\s*\)''', js_code):
        referenced.add(m)
        
    # 3. querySelector('#id') or querySelectorAll('#id')
    for m in re.findall(r'''querySelector(?:All)?\(\s*["']#([a-zA-Z0-9_\-]+)["']\s*\)''', js_code):
        referenced.add(m)
        
    return referenced


@pytest.mark.parametrize("filename", HTML_FILES)
def test_script_syntax_with_node_check(filename: str):
    """Run `node --check` on every inline <script> block in the HTML file."""
    html_path = BASE_DIR / filename
    assert html_path.exists(), f"File {filename} does not exist"
    
    content = html_path.read_text(encoding="utf-8")
    scripts = extract_script_blocks(content)
    assert len(scripts) > 0, f"No inline <script> blocks found in {filename}"
    
    for idx, script_code in enumerate(scripts, start=1):
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as tmp:
            tmp.write(script_code)
            tmp_path = tmp.name
            
        try:
            res = subprocess.run(
                ["node", "--check", tmp_path],
                capture_output=True,
                text=True,
                check=False
            )
            assert res.returncode == 0, (
                f"Syntax error in {filename} <script> block #{idx}:\n"
                f"STDOUT: {res.stdout}\n"
                f"STDERR: {res.stderr}"
            )
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


@pytest.mark.parametrize("filename", HTML_FILES)
def test_all_js_referenced_ids_exist_in_html(filename: str):
    """Verify that every DOM ID referenced in JS exists as an id attribute in the HTML."""
    html_path = BASE_DIR / filename
    assert html_path.exists(), f"File {filename} does not exist"
    
    content = html_path.read_text(encoding="utf-8")
    html_ids = extract_html_ids(content)
    scripts = extract_script_blocks(content)
    
    all_referenced_ids = set()
    for script_code in scripts:
        all_referenced_ids.update(extract_js_referenced_ids(script_code))
        
    missing_ids = all_referenced_ids - html_ids
    assert not missing_ids, (
        f"In {filename}, the following IDs are referenced in JavaScript but NOT defined in the HTML:\n"
        f"{sorted(missing_ids)}\n"
        f"Total referenced IDs: {len(all_referenced_ids)}, total defined HTML IDs: {len(html_ids)}"
    )


if __name__ == "__main__":
    pytest.main(["-v", __file__])
