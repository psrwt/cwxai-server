import re
from html import unescape
from typing import Optional

# Pre-compiled regex patterns for efficient text extraction
CLEANING_PATTERNS = [
    (re.compile(r'<!--.*?-->', re.DOTALL), ''),  # Remove HTML comments
    (re.compile(r'<(script|style)\b.*?>.*?</\1>', re.DOTALL | re.IGNORECASE), ''),  # Remove script and style blocks
    (re.compile(r'<[^>]+/>'), ''),  # Remove self-closing tags
    (re.compile(r'<[^>]+>'), ' '),   # Remove any remaining HTML tags, replacing them with a space
    (re.compile(r'\s+'), ' '),       # Collapse multiple whitespace characters into one space
]

def clean_html_content(
    html: str,
    patterns: Optional[list] = None,
    unescape_entities: bool = True,
    remove_empty_lines: bool = True
) -> str:
    """
    Extract and clean text content from HTML using pre-compiled regex patterns.
    
    Args:
        html: Raw HTML content.
        patterns: Optional list of (compiled_regex, replacement) tuples.
        unescape_entities: If True, convert HTML entities to characters.
        remove_empty_lines: If True, remove empty lines from the result.
        
    Returns:
        Cleaned text content with minimal markup artifacts.
    """
    patterns = patterns or CLEANING_PATTERNS
    for pattern, replacement in patterns:
        html = pattern.sub(replacement, html)
    if unescape_entities:
        html = unescape(html)
    if remove_empty_lines:
        html = "\n".join(line.strip() for line in html.splitlines() if line.strip())
    return html.strip()
