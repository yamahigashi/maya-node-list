"""Generate category index pages from generated node RST files."""

import argparse
import io
import os
import re
from collections import defaultdict


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SOURCE_DIR = os.path.join(ROOT_DIR, "source")
CATEGORY_LINE_RE = re.compile(r"^single:\s*category;\s*(?P<path>.+)$")


def resolve_paths(source_dir):
    # type: (str) -> tuple
    source_dir = os.path.abspath(source_dir)
    nodes_dir = os.path.join(source_dir, "nodes")
    categories_dir = os.path.join(source_dir, "categories")
    category_index_file = os.path.join(categories_dir, "index.rst")
    category_summary_file = os.path.join(categories_dir, "summary.rst")
    return (
        source_dir,
        nodes_dir,
        categories_dir,
        category_index_file,
        category_summary_file,
    )


def parse_args():
    # type: () -> argparse.Namespace
    parser = argparse.ArgumentParser(
        description="Generate source/categories/index.rst from node pages."
    )
    parser.add_argument(
        "--source-dir",
        default=DEFAULT_SOURCE_DIR,
        help="Sphinx source root containing nodes/ (default: {}).".format(
            DEFAULT_SOURCE_DIR
        ),
    )
    return parser.parse_args()


def extract_title(lines):
    # type: (list) -> str
    """Extract node page title from the heading block."""
    for idx, line in enumerate(lines[:-1]):
        text = line.strip()
        if not text or text.startswith("..") or text.startswith(":"):
            continue

        underline = lines[idx + 1].strip()
        if underline and set(underline) == set("="):
            return text

    return None


def parse_node_page(path, source_dir):
    # type: (str, str) -> tuple
    """Return (title, docname, categories) for a node page."""
    with io.open(path, "r", encoding="utf-8") as fp:
        lines = fp.read().splitlines()
    title = extract_title(lines)
    if not title:
        return None

    categories = set()
    for line in lines:
        match = CATEGORY_LINE_RE.match(line.strip())
        if not match:
            continue

        parts = [part.strip() for part in match.group("path").split(";")]
        normalized = "/".join([part for part in parts if part])
        if normalized:
            categories.add(normalized)

    docname = os.path.relpath(path, source_dir)
    docname = os.path.splitext(docname)[0].replace(os.sep, "/")
    return title, docname, categories


def normalize_category(category):
    # type: (str) -> str
    """Normalize category granularity for index readability."""
    parts = [part for part in category.split("/") if part]
    if len(parts) >= 2 and parts[0] == "drawdb":
        return "/".join(parts[:2])
    return "/".join(parts)


def make_category_slug(category):
    # type: (str) -> str
    lowered = category.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "other"


def iter_node_rst_files(nodes_dir):
    # type: (str) -> list
    files = []
    if not os.path.isdir(nodes_dir):
        return files

    for root, _, names in os.walk(nodes_dir):
        for name in names:
            if name.endswith(".rst"):
                files.append(os.path.join(root, name))
    return sorted(files)


def collect_categories(source_dir, nodes_dir):
    # type: (str, str) -> tuple
    """Collect mapping: category -> {docname: title}."""
    category_map = defaultdict(dict)
    node_count = 0

    for path in iter_node_rst_files(nodes_dir):
        parsed = parse_node_page(path, source_dir)
        if parsed is None:
            continue

        title, docname, categories = parsed
        node_count += 1
        for category in categories:
            normalized = normalize_category(category)
            if normalized:
                category_map[normalized][docname] = title

    return category_map, node_count


def build_index_content(category_map):
    # type: (dict) -> str
    lines = [
        ":orphan:",
        "",
        "By Category (classification)",
        "============================",
        "",
    ]

    if not category_map:
        lines.extend(
            [
                "No categories were found.",
                "",
            ]
        )
        return "\n".join(lines)

    for category in sorted(category_map, key=lambda value: value.lower()):
        slug = make_category_slug(category)
        lines.extend(
            [
                ".. _category-{}:".format(slug),
                "",
                category,
                "-" * len(category),
                "",
                ".. container:: category-links",
                "",
            ]
        )

        links = category_map[category]
        sorted_links = sorted(links.items(), key=lambda item: item[1].lower())
        for docname, title in sorted_links:
            safe_title = title.replace("`", r"\`")
            lines.append("   * :doc:`{} </{}>`".format(safe_title, docname))

        lines.append("")

    return "\n".join(lines)


def build_summary_content(category_map):
    # type: (dict) -> str
    lines = []
    for category in sorted(category_map, key=lambda value: value.lower()):
        slug = make_category_slug(category)
        lines.append("* :ref:`{} <category-{}>`".format(category, slug))
    lines.append("")
    return "\n".join(lines)


def generate_for_source(source_dir):
    # type: (str) -> tuple
    (
        source_dir,
        nodes_dir,
        categories_dir,
        category_index_file,
        category_summary_file,
    ) = resolve_paths(source_dir)
    if not os.path.isdir(categories_dir):
        os.makedirs(categories_dir)

    category_map, node_count = collect_categories(source_dir, nodes_dir)
    content = build_index_content(category_map)
    summary_content = build_summary_content(category_map)
    with io.open(category_index_file, "w", encoding="utf-8") as fp:
        fp.write(content)
    with io.open(category_summary_file, "w", encoding="utf-8") as fp:
        fp.write(summary_content)

    return category_index_file, category_summary_file, len(category_map), node_count


def main():
    # type: () -> None
    args = parse_args()
    (
        category_index_file,
        category_summary_file,
        category_count,
        node_count,
    ) = generate_for_source(args.source_dir)
    print(
        "generated {}, {} ({} categories, {} scanned nodes)".format(
            category_index_file, category_summary_file, category_count, node_count
        )
    )


if __name__ == "__main__":
    main()
