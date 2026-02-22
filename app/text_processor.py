"""
Text post-processing applied to markdown returned by Docling before it is
sent back to Open-WebUI.

Mirrors the patch applied to Open-WebUI's main.py loader but runs here so it
works regardless of which loader Open-WebUI is configured to use.

Key difference from the original patch:
  - We do NOT strip markdown image tags ![...](...)  because by this point
    they already point to Azure Blob URLs that we want to keep.
  - We DO strip any remaining base64 data-URIs that slipped through
    (shouldn't happen, but defensive).
"""

import re


class TextProcessor:
    # ── Patterns compiled once at class level ─────────────────────────────────

    # Banners: only lines where the keyword IS the entire content (with optional
    # markdown heading/emphasis markers around it).
    # Matches:  "## INTERNAL ##"  "## INTERNAL"  "**CONFIDENTIAL**"  "--- DRAFT ---"
    # Safe:     "## Internal Architecture ##"  "# Draft Policy"  (has extra words)
    _BANNER_RE = re.compile(
        r"^\s*[#*\-]*\s*(internal|confidential|draft)\s*[#*\-]*\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    # Page footers: "page 3 of 10", "Page 1 of 20", etc.
    _PAGE_FOOTER_RE = re.compile(r"page\s*\d+\s*of\s*\d+", re.IGNORECASE)

    # HTML comments: <!-- ... -->
    _HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

    # Base64 data-URI images that were not replaced (defensive fallback)
    _BASE64_IMAGE_RE = re.compile(
        r'!\[.*?\]\(data:image/[^;]+;base64,[A-Za-z0-9+/=\s]+?\)',
        re.DOTALL,
    )

    # Excessive blank lines → single blank line
    _MULTI_NEWLINE_RE = re.compile(r"\n\s*\n+")

    # Multiple spaces / tabs → single space
    _MULTI_SPACE_RE = re.compile(r"[ \t]+")

    def process(self, text: str) -> str:
        # 1. Remove standalone banner lines — only lines where the keyword IS
        #    the entire content (with optional # * - markers around it).
        #    ✅ "## INTERNAL ##"   → wiped
        #    ✅ "**CONFIDENTIAL**" → wiped
        #    ✅ "--- DRAFT ---"    → wiped
        #    ✅ "## Internal Architecture ##" → kept  (has extra words after)
        #    ✅ "# Draft Policy"              → kept  (has extra words after)
        text = self._BANNER_RE.sub("", text)

        # 2. Remove page footers ("page 3 of 10")
        #    ⚠️  COMMENTED OUT — can mangle sentences like
        #    "see page 3 of 10 examples" mid-paragraph.
        # text = self._PAGE_FOOTER_RE.sub("", text)

        # 3. Remove HTML comments <!-- ... -->
        #    ✅ Safe — invisible in rendered markdown and not meaningful for RAG.
        text = self._HTML_COMMENT_RE.sub("", text)

        # 4. Remove any leftover base64 images (safety net — should already
        #    have been replaced by image_processor.py)
        #    ✅ Safe — these would massively bloat the vector DB if left in.
        text = self._BASE64_IMAGE_RE.sub("", text)

        # 5. Collapse excessive blank lines
        #    ⚠️  COMMENTED OUT — can break intentional spacing in poetry,
        #    structured lists, or documents that use whitespace semantically.
        # text = self._MULTI_NEWLINE_RE.sub("\n\n", text)

        # 6. Normalize horizontal whitespace (multiple spaces/tabs → single space)
        #    ⚠️  COMMENTED OUT — high risk: destroys markdown table column
        #    alignment and any indented content outside fenced code blocks.
        # text = self._MULTI_SPACE_RE.sub(" ", text)

        # 7. Strip leading/trailing whitespace
        #    ✅ Safe — never meaningful at document boundaries.
        return text.strip()


# Module-level singleton — import and call directly
processor = TextProcessor()
