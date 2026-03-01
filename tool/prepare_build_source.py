#!/usr/bin/env python
"""Prepare Sphinx build source from versioned dump output."""

import argparse
import os
import re
import shutil

import generate_category_index as category_index

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DATA_ROOT = os.path.join(ROOT_DIR, "data", "nodes")
DEFAULT_SOURCE_ROOT = os.path.join(ROOT_DIR, "source")
DEFAULT_OUTPUT_ROOT = os.path.join(ROOT_DIR, "build", "source")
YEAR_PATTERN = re.compile(r"^\d{4}$")


def parse_args():
    # type: () -> argparse.Namespace
    parser = argparse.ArgumentParser(
        description="Build temporary Sphinx source from data/nodes/<version>."
    )
    parser.add_argument(
        "--version",
        default="",
        help="Version directory under data/nodes (default: MAYA_VERSION env or latest).",
    )
    parser.add_argument(
        "--data-root",
        default=DEFAULT_DATA_ROOT,
        help="Versioned dump root (default: {}).".format(DEFAULT_DATA_ROOT),
    )
    parser.add_argument(
        "--source-root",
        default=DEFAULT_SOURCE_ROOT,
        help="Base Sphinx source root (default: {}).".format(DEFAULT_SOURCE_ROOT),
    )
    parser.add_argument(
        "--output-root",
        default=DEFAULT_OUTPUT_ROOT,
        help="Prepared Sphinx source output (default: {}).".format(DEFAULT_OUTPUT_ROOT),
    )
    return parser.parse_args()


def list_available_versions(data_root):
    # type: (str) -> list
    if not os.path.isdir(data_root):
        return []

    versions = []
    for name in os.listdir(data_root):
        path = os.path.join(data_root, name)
        if os.path.isdir(path):
            versions.append(name)

    def sort_key(value):
        if YEAR_PATTERN.match(value):
            return (0, -int(value))
        return (1, value)

    return sorted(versions, key=sort_key)


def resolve_version(requested, data_root):
    # type: (str, str) -> str
    normalized = (requested or "").strip()
    if normalized:
        return normalized

    env_version = os.getenv("MAYA_VERSION", "").strip()
    if env_version:
        return env_version

    versions = list_available_versions(data_root)
    if not versions:
        raise IOError("No version directories found in {}".format(data_root))

    return versions[0]


def prepare_output_root(source_root, output_root):
    # type: (str, str) -> None
    if not os.path.isdir(source_root):
        raise IOError("source root not found: {}".format(source_root))

    if os.path.isdir(output_root):
        shutil.rmtree(output_root)

    # source/nodes is no longer a build input.
    shutil.copytree(source_root, output_root, ignore=shutil.ignore_patterns("nodes"))


def count_rst_files(nodes_dir):
    # type: (str) -> int
    rst_count = 0
    for root, _, files in os.walk(nodes_dir):
        for name in files:
            if name.endswith(".rst"):
                rst_count += 1
    return rst_count


def inject_version_nodes(version, data_root, output_root):
    # type: (str, str, str) -> int
    source_nodes = os.path.join(data_root, version)
    if not os.path.isdir(source_nodes):
        available = ", ".join(list_available_versions(data_root)) or "(none)"
        raise IOError(
            "Version directory not found: {}\nAvailable versions: {}".format(
                source_nodes, available
            )
        )

    output_nodes = os.path.join(output_root, "nodes")
    shutil.copytree(source_nodes, output_nodes)
    return count_rst_files(output_nodes)


def main():
    # type: () -> int
    args = parse_args()
    data_root = os.path.abspath(args.data_root)
    source_root = os.path.abspath(args.source_root)
    output_root = os.path.abspath(args.output_root)
    version = resolve_version(args.version, data_root)

    print("[prepare] version: {}".format(version))
    print("[prepare] data:    {}".format(os.path.join(data_root, version)))
    print("[prepare] source:  {}".format(source_root))
    print("[prepare] output:  {}".format(output_root))

    prepare_output_root(source_root, output_root)
    rst_count = inject_version_nodes(version, data_root, output_root)
    (
        category_file,
        category_summary_file,
        category_count,
        node_count,
    ) = category_index.generate_for_source(output_root)

    print("[prepare] copied {} rst files".format(rst_count))
    print(
        "[prepare] categories {}, {} ({} categories, {} scanned nodes)".format(
            category_file, category_summary_file, category_count, node_count
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
