#!/usr/bin/env python
"""Publish built HTML docs to versioned GitHub Pages paths.

Usage example:
    python tool/publish_version_site.py \
        --version 2026 \
        --site-dir build/html \
        --publish-root .
"""

import argparse
import io
import json
import os
import re
import shutil
from datetime import datetime, timezone

VERSION_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
YEAR_VERSION_PATTERN = re.compile(r"^\d{4}$")
TITLE_PATTERN = re.compile(r"^(?P<plugin>.+?)\s-\s(?P<type_name>.+?)\s\((?P<type_id>0x[0-9a-fA-F]+)\)$")
ATTR_ROW_PATTERN = re.compile(
    r'<tr[^>]*>\s*'
    r'.*?<td class="attr_name"[^>]*><span class="attr_label">(?P<label>[^<]+)</span></td>\s*'
    r'<td class="attr_type">(?P<attr_type>.*?)</td>\s*'
    r'<td class="attr_value">(?P<attr_value>.*?)</td>\s*'
    r'<td class="attr_minmax">(?P<attr_minmax>.*?)</td>\s*'
    r'<td class="attr_flags">(?P<attr_flags>.*?)</td>\s*'
    r"</tr>",
    re.DOTALL,
)
ATTR_LABEL_PATTERN = re.compile(r"^(?P<name>.+)\s\((?P<short_name>[^()]*)\)$")
TAG_PATTERN = re.compile(r"<[^>]+>")


def utc_now_iso():
    # type: () -> str
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args():
    # type: () -> argparse.Namespace
    parser = argparse.ArgumentParser(
        description="Publish Sphinx HTML output into versioned directories."
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Version label used as target directory name (for example: 2026).",
    )
    parser.add_argument(
        "--site-dir",
        default="build/html",
        help="Built HTML directory (default: build/html).",
    )
    parser.add_argument(
        "--publish-root",
        default=".",
        help="Root directory of the published site (default: current dir).",
    )
    parser.add_argument(
        "--data-root",
        default=os.path.join("data", "nodes"),
        help="Versioned dump root containing manifests (default: data/nodes).",
    )
    parser.add_argument(
        "--latest-alias",
        default="latest",
        help="Directory name for latest pointer (default: latest).",
    )
    parser.add_argument(
        "--set-latest",
        dest="set_latest",
        action="store_true",
        help="Update latest alias directory (default: enabled).",
    )
    parser.add_argument(
        "--no-set-latest",
        dest="set_latest",
        action="store_false",
        help="Do not update latest alias directory.",
    )
    parser.add_argument(
        "--write-root-index",
        dest="write_root_index",
        action="store_true",
        help="Write root index.html landing page (default: enabled).",
    )
    parser.add_argument(
        "--no-write-root-index",
        dest="write_root_index",
        action="store_false",
        help="Do not write root index.html landing page.",
    )
    parser.add_argument(
        "--write-versions-index",
        dest="write_versions_index",
        action="store_true",
        help="Write versions/index.html and versions.json (default: enabled).",
    )
    parser.add_argument(
        "--no-write-versions-index",
        dest="write_versions_index",
        action="store_false",
        help="Do not write versions/index.html or versions.json.",
    )
    parser.set_defaults(
        set_latest=True,
        write_root_index=True,
        write_versions_index=True,
    )
    return parser.parse_args()


def validate_version_name(version):
    # type: (str) -> str
    normalized = version.strip()
    if not normalized:
        raise ValueError("Version must not be empty.")
    if not VERSION_NAME_PATTERN.match(normalized):
        raise ValueError(
            "Version can contain only letters, numbers, dot, underscore, hyphen."
        )
    return normalized


def sync_tree(source, target):
    # type: (str, str) -> None
    if os.path.exists(target):
        shutil.rmtree(target)
    shutil.copytree(source, target)


def discover_year_versions(publish_root):
    # type: (str) -> list
    versions = []
    if not os.path.isdir(publish_root):
        return versions

    for name in os.listdir(publish_root):
        path = os.path.join(publish_root, name)
        if not os.path.isdir(path):
            continue
        if not YEAR_VERSION_PATTERN.match(name):
            continue
        if not os.path.isfile(os.path.join(path, "index.html")):
            continue
        versions.append(name)
    versions.sort(key=int, reverse=True)
    return versions


def render_root_index(latest_version, versions):
    # type: (str, list) -> str
    latest_path = "./latest/"
    title_suffix = " ({})".format(latest_version) if latest_version else ""
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>maya-node-list latest{title_suffix}</title>
  <meta http-equiv="refresh" content="0; url={latest_path}">
  <script>location.replace("{latest_path}");</script>
</head>
<body>
  <p>Redirecting to latest docs... <a href="{latest_path}">Continue</a></p>
</body>
</html>
""".format(
        title_suffix=title_suffix, latest_path=latest_path
    )


def render_versions_index(latest_version, versions):
    # type: (str, list) -> str
    if latest_version:
        latest_line = "<p>Latest: <strong>{}</strong></p>".format(latest_version)
    else:
        latest_line = "<p>Latest: not set</p>"

    rows = "\n".join(
        ["<li><a href='../{0}/'>{0}</a></li>".format(version) for version in versions]
    ) or "<li>No published versions yet.</li>"
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Versions - maya-node-list</title>
</head>
<body>
  <h1>Published Versions</h1>
  {latest_line}
  <ul>
    {rows}
  </ul>
  <p><a href="../">Back to root</a></p>
</body>
</html>
""".format(
        latest_line=latest_line, rows=rows
    )


def write_text(path, data):
    # type: (str, str) -> None
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(path, "w", encoding="utf-8") as fp:
        fp.write(data)


def write_json(path, payload):
    # type: (str, dict) -> None
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, sort_keys=True)
        fp.write("\n")


def read_json(path):
    # type: (str) -> dict
    if not os.path.isfile(path):
        return {}
    with io.open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def strip_tags(text):
    # type: (str) -> str
    return TAG_PATTERN.sub("", text or "").strip()


def normalize_scalar(value):
    # type: (str) -> str
    text = (value or "").strip()
    if text in ("", "()", "None", "null"):
        return ""
    return text


def normalize_flags(flags_text):
    # type: (str) -> list
    parts = [part.strip() for part in (flags_text or "").split(",")]
    parts = [part for part in parts if part and part != "-"]
    return sorted(set(parts))


def parse_value_cell(value_text):
    # type: (str) -> tuple
    text = normalize_scalar(value_text)
    if not text:
        return "", ""

    if "default:" in text:
        parts = [part.strip() for part in text.split("default:", 1)]
        current = normalize_scalar(parts[0])
        default = normalize_scalar(parts[1] if len(parts) > 1 else "")
        return current, default

    match = re.match(r"^(?P<current>.*?)\s*\((?P<default>.*?)\)\s*$", text)
    if match:
        current = normalize_scalar(match.group("current"))
        default = normalize_scalar(match.group("default"))
        return current, default
    return text, ""


def parse_minmax_cell(minmax_text):
    # type: (str) -> tuple
    text = normalize_scalar(minmax_text)
    if not text:
        return "", ""
    if "/" not in text:
        return normalize_scalar(text), ""
    left, right = text.split("/", 1)
    return normalize_scalar(left), normalize_scalar(right)


def parse_classification(lines):
    # type: (list) -> str
    collecting = False
    values = []
    for raw in lines:
        stripped = raw.strip()
        if stripped == ":classification:":
            collecting = True
            continue
        if collecting and stripped.startswith(":"):
            break
        if collecting and stripped and stripped != "(none)":
            values.append(stripped)
    return ":".join(values)


def parse_title(lines):
    # type: (list) -> tuple
    for idx in range(len(lines) - 1):
        text = lines[idx].strip()
        underline = lines[idx + 1].strip()
        if not text:
            continue
        if not underline or set(underline) != set("="):
            continue
        match = TITLE_PATTERN.match(text)
        if not match:
            continue
        return match.group("plugin"), match.group("type_name"), match.group("type_id")
    return "", "", ""


def parse_attributes_from_rst(text):
    # type: (str) -> list
    attrs = []
    for match in ATTR_ROW_PATTERN.finditer(text):
        raw_label = strip_tags(match.group("label"))
        label_match = ATTR_LABEL_PATTERN.match(raw_label)
        if label_match:
            name = label_match.group("name").strip()
            short_name = label_match.group("short_name").strip()
        else:
            name = raw_label.strip()
            short_name = ""

        attr_type = normalize_scalar(strip_tags(match.group("attr_type")))
        value_text = strip_tags(match.group("attr_value"))
        current_value, default_value = parse_value_cell(value_text)
        min_value, max_value = parse_minmax_cell(strip_tags(match.group("attr_minmax")))
        flags = normalize_flags(strip_tags(match.group("attr_flags")))

        attrs.append(
            {
                "name": name,
                "shortName": short_name,
                "type": attr_type,
                "value": current_value,
                "default": default_value,
                "min": min_value,
                "max": max_value,
                "enum": "",
                "parent": "",
                "flags": flags,
            }
        )

    attrs.sort(key=lambda item: item["name"].lower())
    return attrs


def list_rst_files(version_dir):
    # type: (str) -> list
    files = []
    for root, _, names in os.walk(version_dir):
        for name in names:
            if name.endswith(".rst"):
                files.append(os.path.join(root, name))
    return sorted(files)


def build_manifest_from_rst(data_root, version):
    # type: (str, str) -> dict
    version_dir = os.path.join(data_root, version)
    nodes = []
    for path in list_rst_files(version_dir):
        with io.open(path, "r", encoding="utf-8") as fp:
            text = fp.read()
        lines = text.splitlines()
        plugin_from_title, type_name, type_id = parse_title(lines)
        if not type_id:
            continue

        classification = parse_classification(lines)
        plugin_dir_name = os.path.basename(os.path.dirname(path))
        plugin = plugin_from_title or plugin_dir_name
        plugin = plugin.strip() or plugin_dir_name
        plugin = os.path.basename(plugin)

        attributes = parse_attributes_from_rst(text)
        nodes.append(
            {
                "typeId": type_id.lower(),
                "typeName": type_name.strip(),
                "plugin": plugin,
                "classification": classification,
                "attributeCount": len(attributes),
                "attributes": attributes,
            }
        )

    nodes.sort(key=lambda item: item["typeId"])
    payload = {
        "version": version,
        "generated_at_utc": utc_now_iso(),
        "node_count": len(nodes),
        "nodes": nodes,
        "generated_from": "rst_fallback",
    }
    manifest_path = os.path.join(version_dir, "manifest.json")
    write_json(manifest_path, payload)
    return payload


def load_manifest_payload(data_root, version):
    # type: (str, str) -> dict
    manifest_path = os.path.join(data_root, version, "manifest.json")
    payload = read_json(manifest_path)
    if payload:
        return payload
    return build_manifest_from_rst(data_root, version)


def load_failures_payload(data_root, version):
    # type: (str, str) -> dict
    failures_path = os.path.join(data_root, version, "failures.json")
    payload = read_json(failures_path)
    if payload:
        return payload
    payload = {
        "version": version,
        "generated_at_utc": utc_now_iso(),
        "failure_count": 0,
        "failures": [],
        "generated_from": "rst_fallback",
    }
    write_json(failures_path, payload)
    return payload


def map_nodes_by_type_id(manifest_payload):
    # type: (dict) -> dict
    nodes = manifest_payload.get("nodes", []) if manifest_payload else []
    mapped = {}
    for node in nodes:
        node_id = str(node.get("typeId", "")).lower()
        if not node_id:
            continue
        mapped[node_id] = node
    return mapped


def map_attributes_by_name(node_payload):
    # type: (dict) -> dict
    attrs = node_payload.get("attributes", []) if node_payload else []
    mapped = {}
    for attr in attrs:
        name = str(attr.get("name", "")).strip()
        if not name:
            continue
        mapped[name] = attr
    return mapped


def normalize_failure_type_ids(failures_payload):
    # type: (dict) -> list
    failures = failures_payload.get("failures", []) if failures_payload else []
    type_ids = []
    for item in failures:
        type_id = str(item.get("typeId", "")).strip().lower()
        if type_id:
            type_ids.append(type_id)
    return sorted(set(type_ids))


def build_attribute_changes(new_attr, old_attr):
    # type: (dict, dict) -> dict
    changed = {}
    compare_fields = ["type", "default", "flags", "min", "max", "enum"]
    for field in compare_fields:
        new_value = new_attr.get(field)
        old_value = old_attr.get(field)
        if new_value != old_value:
            changed[field] = {
                "old": old_value,
                "new": new_value,
            }
    return changed


def build_attribute_diff(new_node, old_node):
    # type: (dict, dict) -> dict
    new_attrs = map_attributes_by_name(new_node)
    old_attrs = map_attributes_by_name(old_node)

    new_names = set(new_attrs.keys())
    old_names = set(old_attrs.keys())

    added_names = sorted(new_names - old_names)
    removed_names = sorted(old_names - new_names)

    changed = {}
    common_names = sorted(new_names & old_names)
    for name in common_names:
        detail = build_attribute_changes(new_attrs[name], old_attrs[name])
        if detail:
            changed[name] = detail

    return {
        "summary": {
            "added": len(added_names),
            "removed": len(removed_names),
            "changed": len(changed),
        },
        "added": added_names,
        "removed": removed_names,
        "changed": changed,
    }


def build_node_diff_entry(new_node, old_node):
    # type: (dict, dict) -> dict
    node_changes = {}
    meta_fields = ["typeName", "plugin", "classification"]
    for field in meta_fields:
        new_value = new_node.get(field)
        old_value = old_node.get(field)
        if new_value != old_value:
            node_changes[field] = {
                "old": old_value,
                "new": new_value,
            }

    attribute_diff = build_attribute_diff(new_node, old_node)
    attr_summary = attribute_diff["summary"]
    has_attr_changes = (
        attr_summary["added"] > 0
        or attr_summary["removed"] > 0
        or attr_summary["changed"] > 0
    )
    if not node_changes and not has_attr_changes:
        return {}

    return {
        "typeName": new_node.get("typeName"),
        "plugin": new_node.get("plugin"),
        "classification": new_node.get("classification"),
        "node_changes": node_changes,
        "attribute_summary": attr_summary,
        "attributes": {
            "added": attribute_diff["added"],
            "removed": attribute_diff["removed"],
            "changed": attribute_diff["changed"],
        },
    }


def build_version_diff_payload(
    data_root, new_version, previous_version, manifest_cache=None, failures_cache=None
):
    # type: (str, str, str) -> dict
    if manifest_cache is None:
        manifest_cache = {}
    if failures_cache is None:
        failures_cache = {}

    if new_version not in manifest_cache:
        manifest_cache[new_version] = load_manifest_payload(data_root, new_version)
    if previous_version not in manifest_cache:
        manifest_cache[previous_version] = load_manifest_payload(
            data_root, previous_version
        )
    if new_version not in failures_cache:
        failures_cache[new_version] = load_failures_payload(data_root, new_version)
    if previous_version not in failures_cache:
        failures_cache[previous_version] = load_failures_payload(
            data_root, previous_version
        )

    new_manifest = manifest_cache[new_version]
    previous_manifest = manifest_cache[previous_version]
    new_failures = failures_cache[new_version]
    previous_failures = failures_cache[previous_version]

    new_nodes = map_nodes_by_type_id(new_manifest)
    old_nodes = map_nodes_by_type_id(previous_manifest)

    new_ids = set(new_nodes.keys())
    old_ids = set(old_nodes.keys())

    added_type_ids = sorted(new_ids - old_ids)
    removed_type_ids = sorted(old_ids - new_ids)
    common_ids = sorted(new_ids & old_ids)
    added_nodes = [
        {
            "typeId": type_id,
            "typeName": new_nodes[type_id].get("typeName"),
            "plugin": new_nodes[type_id].get("plugin"),
        }
        for type_id in added_type_ids
    ]
    removed_nodes = [
        {
            "typeId": type_id,
            "typeName": old_nodes[type_id].get("typeName"),
            "plugin": old_nodes[type_id].get("plugin"),
        }
        for type_id in removed_type_ids
    ]

    changed = {}
    unchanged_count = 0
    for type_id in common_ids:
        entry = build_node_diff_entry(new_nodes[type_id], old_nodes[type_id])
        if entry:
            changed[type_id] = entry
        else:
            unchanged_count += 1

    failed_new_type_ids = normalize_failure_type_ids(new_failures)
    failed_previous_type_ids = normalize_failure_type_ids(previous_failures)

    return {
        "new_version": new_version,
        "previous_version": previous_version,
        "generated_at_utc": utc_now_iso(),
        "summary": {
            "added": len(added_type_ids),
            "removed": len(removed_type_ids),
            "changed": len(changed),
            "unchanged": unchanged_count,
            "failed_new": len(failed_new_type_ids),
            "failed_previous": len(failed_previous_type_ids),
        },
        "node_diff": {
            "added_type_ids": added_type_ids,
            "added_nodes": added_nodes,
            "removed_type_ids": removed_type_ids,
            "removed_nodes": removed_nodes,
            "changed": changed,
            "failed_new_type_ids": failed_new_type_ids,
            "failed_previous_type_ids": failed_previous_type_ids,
        },
    }


def write_version_diffs(publish_root, data_root, versions):
    # type: (str, str, list) -> list
    written = []
    if len(versions) < 2:
        return written
    total_pairs = len(versions) - 1

    diff_root = os.path.join(publish_root, "versions", "diff")
    if os.path.isdir(diff_root):
        shutil.rmtree(diff_root)
    os.makedirs(diff_root)

    manifest_cache = {}
    failures_cache = {}

    for idx in range(len(versions) - 1):
        new_version = versions[idx]
        previous_version = versions[idx + 1]
        pair_index = idx + 1
        print(
            "[publish] diff {}/{}: {} <- {}".format(
                pair_index, total_pairs, new_version, previous_version
            ),
            flush=True,
        )
        payload = build_version_diff_payload(
            data_root,
            new_version,
            previous_version,
            manifest_cache,
            failures_cache,
        )
        filename = "{}-vs-{}.json".format(new_version, previous_version)
        path = os.path.join(diff_root, filename)
        write_json(path, payload)
        written.append(path)

    return written


def main():
    # type: () -> int
    args = parse_args()
    version = validate_version_name(args.version)
    site_dir = os.path.abspath(args.site_dir)
    publish_root = os.path.abspath(args.publish_root)
    data_root = os.path.abspath(args.data_root)
    latest_alias = args.latest_alias.strip() or "latest"

    if not os.path.isdir(site_dir):
        raise IOError("site directory not found: {}".format(site_dir))
    if not os.path.isfile(os.path.join(site_dir, "index.html")):
        raise IOError("index.html not found in site directory: {}".format(site_dir))
    if "/" in latest_alias or "\\" in latest_alias:
        raise ValueError("latest alias must be a single directory name.")

    if not os.path.isdir(publish_root):
        os.makedirs(publish_root)
    open(os.path.join(publish_root, ".nojekyll"), "a").close()

    target_version_dir = os.path.join(publish_root, version)
    print("[publish] sync version: {} -> {}".format(site_dir, target_version_dir))
    sync_tree(site_dir, target_version_dir)

    if args.set_latest:
        latest_dir = os.path.join(publish_root, latest_alias)
        print("[publish] sync latest: {} -> {}".format(site_dir, latest_dir))
        sync_tree(site_dir, latest_dir)

    print("[publish] discovering versions in {}".format(publish_root))
    versions = discover_year_versions(publish_root)
    print("[publish] discovered versions: {}".format(", ".join(versions) or "none"))
    latest_version = versions[0] if versions else None
    print("[publish] found versions: {}".format(", ".join(versions) or "none"))
    written_diffs = write_version_diffs(publish_root, data_root, versions)
    for path in written_diffs:
        print("[publish] wrote {}".format(path))
    print("[publish] generated {} version diff files.".format(len(written_diffs)))

    if args.write_versions_index:
        print("[publish] writing versions index and metadata")
        versions_dir = os.path.join(publish_root, "versions")
        versions_index = render_versions_index(latest_version, versions)
        write_text(os.path.join(versions_dir, "index.html"), versions_index)
        print("[publish] wrote {}".format(os.path.join(versions_dir, "index.html")))

        versions_json = {
            "latest": latest_version,
            "versions": versions,
            "generated_at_utc": utc_now_iso(),
        }
        print("[publish] writing versions metadata")
        write_text(
            os.path.join(versions_dir, "versions.json"),
            json.dumps(versions_json, indent=2),
        )
        print("[publish] wrote {}".format(os.path.join(versions_dir, "index.html")))
        print("[publish] wrote {}".format(os.path.join(versions_dir, "versions.json")))

    if args.write_root_index:
        root_index = render_root_index(latest_version, versions)
        write_text(os.path.join(publish_root, "index.html"), root_index)
        print("[publish] wrote {}".format(os.path.join(publish_root, "index.html")))

    print("[publish] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
