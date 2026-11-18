"""Resolve rendered CommonMark link and image URLs to project paths."""

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit


class MarkdownUnavailable(RuntimeError):
    """The Markdown checks require the optional parser."""


@dataclass(frozen=True)
class ProjectTarget:
    href: str
    path: str
    directory_required: bool

    def matches_kind(self, kind):
        return kind == "directory" or (kind == "file" and not self.directory_required)


def project_target(document, href):
    """Return a canonical target, None for excluded URLs, or raise if indeterminate."""
    uri = urlsplit(href)
    if uri.scheme or uri.netloc or not uri.path or uri.path.startswith("/"):
        return None

    segments = [unquote(part, errors="strict") for part in uri.path.split("/")]
    parts = list(PurePosixPath(document).parent.parts)
    for index, segment in enumerate(segments):
        if segment == "..":
            if not parts:
                raise ValueError(f"relative Markdown URL leaves the project: {href}")
            parts.pop()
        elif segment == "." or (segment == "" and index == len(segments) - 1):
            continue
        else:
            if not segment or any(c in '/\\:' or ord(c) < 32 for c in segment):
                raise ValueError(f"unsupported relative Markdown path: {href}")
            parts.append(segment)

    return ProjectTarget(href, "/".join(parts) or ".", segments[-1] in ("", ".", ".."))


class MarkdownPaths:
    dialect = "CommonMark"
    html_enabled = False

    def __init__(self):
        try:
            from markdown_it import MarkdownIt

            self.version = version("markdown-it-py")
        except (ImportError, PackageNotFoundError) as error:
            raise MarkdownUnavailable(
                "Markdown checks require markdown-it-py; install scripts/requirements.txt"
            ) from error
        self.parser = MarkdownIt("commonmark", {"html": self.html_enabled})

    def evidence(self):
        return {
            "parser": "markdown-it-py",
            "version": self.version,
            "dialect": self.dialect,
            "raw_html": self.html_enabled,
            "scope": "relative paths of rendered link and image nodes",
            "query_and_fragment_checked": False,
        }

    def project_targets(self, document, text):
        # The parser's default nesting limit silently skips some content.
        # A document cannot contain more nested delimiters than characters.
        self.parser.options["maxNesting"] = len(text) + 1
        for block in self.parser.parse(text):
            if block.type != "inline":
                continue
            line = block.map[0] + 1 if block.map else None
            for token in block.children or ():
                if token.type == "link_open":
                    target = token.attrGet("href")
                elif token.type == "image":
                    target = token.attrGet("src")
                else:
                    continue
                if not isinstance(target, str):
                    raise ValueError("Markdown link node has no destination")
                resolved = project_target(document, target)
                if resolved is not None:
                    yield line, resolved
