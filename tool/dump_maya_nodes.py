##############################################################################
# Dump Maya nodes and generate versioned node RST files.
#
# The default path resolves registered node types deterministically from
# `allNodeTypes()` and then looks up each `MTypeId` via `MNodeClass`.
##############################################################################
import os
import re
import io
import glob
import sys
import json
import traceback
from collections import OrderedDict
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

import maya.standalone


try:
    maya.standalone.initialize(name='python')
except Exception as e:
    traceback.print_exc()
    print(e)


import maya.api.OpenMaya as om2
import maya.cmds as cmds


##############################################################################
root_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(root_dir)
template_dir = os.path.join(project_root, "source", "_templates")

env = Environment(loader=FileSystemLoader(template_dir, encoding="utf8"))
tmpl = env.get_template("node.tpl.rst")


##############################################################################
DANGEROUS_PLUGINS = [
    "sceneAssembly",
    "mtoa",
    # "bifrostshellnode",
    # "bifmeshio",
    # "bifrostvisplugin",
    # "bifrostgraph",
]

DANGEROUS_PLUGIN_KEYWORDS = (
    "arnold",
    # "bifrost",
)

DANGEROUS_NODES = [
    # "bifShape",  # can cause Maya to crash when created
    # "bifrostGeoToMaya",  # can cause Maya to crash when created
]
USER_SKIPPED_NODES = {
    n.strip() for n in os.getenv("DUMP_SKIP_NODE_TYPES", "").split(",") if n.strip()
}
CREATE_NODE_INSTANCE = os.getenv("DUMP_CREATE_NODE_INSTANCE", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
FORCE_OS_EXIT_ON_PY2 = os.getenv("DUMP_FORCE_OS_EXIT_ON_PY2", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


##############################################################################
def resolve_maya_docs_year():
    env_year = os.getenv("MAYA_VERSION", "").strip()
    if re.match(r"^\d{4}$", env_year):
        return env_year

    maya_version = cmds.about(version=True) or ""
    match = re.search(r"(20\d{2})", maya_version)
    if match:
        return match.group(1)

    # Fallback for non-standard environments.
    return "2016"


def resolve_dump_version():
    # type: () -> str
    requested = os.getenv("MAYA_VERSION", "").strip()
    if requested:
        return requested
    return resolve_maya_docs_year()


MAYA_DOCS_YEAR = resolve_maya_docs_year()
MAYA_DOCS_BASE_URL = "https://help.autodesk.com/cloudhelp/{}/ENU/Maya-Tech-Docs/Nodes".format(
    MAYA_DOCS_YEAR
)
DUMP_VERSION = resolve_dump_version()
output_dir = os.path.join(project_root, "data", "nodes", DUMP_VERSION)
manifest_file = os.path.join(output_dir, "manifest.json")
failures_file = os.path.join(output_dir, "failures.json")
print("Dump version: {}".format(DUMP_VERSION))
print("Output directory: {}".format(output_dir))


##############################################################################
ABSTRACT_SUFFIX = " (abstract)"

try:
    string_types = (basestring,)  # type: ignore[name-defined]
except NameError:
    string_types = (str,)

try:
    text_type = unicode  # type: ignore[name-defined]
except NameError:
    text_type = str


def utc_now_iso():
    # type: () -> str
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def to_text(value):
    # type: (object) -> str
    if value is None:
        return ""
    if isinstance(value, string_types):
        text = value
    else:
        text = str(value)
    return text.strip()


def normalize_scalar(value):
    # type: (object) -> str
    text = to_text(value)
    if text in ("", "()", "None", "null"):
        return ""
    return text


def normalize_flags(flags):
    # type: (list) -> list
    uniq = sorted(set([to_text(flag) for flag in (flags or []) if to_text(flag)]))
    return uniq


def normalize_plugin_name(plugin_name):
    # type: (str) -> str
    name = to_text(plugin_name)
    if not name:
        return "_default"
    return os.path.basename(name)


def format_minmax_display(min_value, max_value):
    # type: (str, str) -> str
    if not min_value and not max_value:
        return "-"
    if min_value and max_value:
        return "{}/{}".format(min_value, max_value)
    if min_value:
        return "{}/-".format(min_value)
    return "-/{}".format(max_value)


def display_or_dash(value):
    # type: (str) -> str
    return value if value else "-"


def normalize_numeric_token(value):
    # type: (object) -> str
    text = to_text(value)
    if not text:
        return ""

    try:
        return str(int(text, 0))
    except (TypeError, ValueError):
        pass

    try:
        as_float = float(text)
    except (TypeError, ValueError):
        return text

    if as_float.is_integer():
        return str(int(as_float))
    return text


def parse_enum_items(enum_text, default_value):
    # type: (str, str) -> list
    normalized_enum = normalize_scalar(enum_text)
    if not normalized_enum:
        return []

    default_text = normalize_scalar(default_value)
    default_norm = normalize_numeric_token(default_text).lower()
    default_name = default_text.lower()
    tokens = [token.strip() for token in normalized_enum.split(":") if token.strip()]

    items = []
    next_value = 0
    for token in tokens:
        label = token
        value_text = ""

        if "=" in token:
            name_part, value_part = token.split("=", 1)
            label = to_text(name_part) or token
            value_text = to_text(value_part)
            try:
                next_value = int(value_text, 0) + 1
            except (TypeError, ValueError):
                next_value = None
        else:
            label = to_text(token)
            if next_value is not None:
                value_text = str(next_value)
                next_value += 1

        item_label = label
        if value_text:
            item_label = "{} ({})".format(label, value_text)

        is_default = False
        if default_text:
            if label.lower() == default_name:
                is_default = True
            elif value_text:
                enum_value_norm = normalize_numeric_token(value_text).lower()
                is_default = enum_value_norm == default_norm

        items.append(
            {
                "name": label,
                "value": value_text,
                "label": item_label,
                "is_default": is_default,
            }
        )

    return items


def make_failure_record(raw_id, type_name, stage, error):
    # type: (int, str, str, object) -> dict
    return {
        "typeId": hex(raw_id),
        "typeName": to_text(type_name) or "<unknown>",
        "stage": to_text(stage) or "unknown",
        "error": to_text(error) or "unknown error",
    }


def write_json_file(path, payload):
    # type: (str, dict) -> None
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))

    json_text = json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    )
    if not isinstance(json_text, text_type):
        json_text = json_text.decode("utf-8")

    with io.open(path, "w", encoding="utf-8") as fp:
        fp.write(json_text)
        fp.write(u"\n")


def write_dump_artifacts(manifest_nodes, failures):
    # type: (list, list) -> None
    manifest_payload = {
        "version": DUMP_VERSION,
        "generated_at_utc": utc_now_iso(),
        "node_count": len(manifest_nodes),
        "nodes": manifest_nodes,
    }
    failures_payload = {
        "version": DUMP_VERSION,
        "generated_at_utc": utc_now_iso(),
        "failure_count": len(failures),
        "failures": failures,
    }

    write_json_file(manifest_file, manifest_payload)
    write_json_file(failures_file, failures_payload)
    print("Wrote {}".format(manifest_file))
    print("Wrote {}".format(failures_file))


def collapse_result(result, manifest_nodes, failures):
    # type: (dict, list, list) -> None
    if not result:
        return
    manifest_node = result.get("manifest_node")
    failure = result.get("failure")
    if manifest_node:
        manifest_nodes.append(manifest_node)
    if failure:
        failures.append(failure)


def print_processing_summary(total_targets, manifest_nodes, failures):
    # type: (int, list, list) -> None
    print(
        "Processing summary: targets={}, written={}, failed={}".format(
            total_targets, len(manifest_nodes), len(failures)
        )
    )


def mtypeid_to_int(type_id):
    """Convert Maya's MTypeId object to a plain int."""
    raw_id = getattr(type_id, "id", None)
    if callable(raw_id):
        return int(raw_id())
    if raw_id is not None:
        return int(raw_id)

    try:
        return int(type_id)
    except (TypeError, ValueError):
        match = re.search(r"0x[0-9a-fA-F]+|\d+", str(type_id))
        if not match:
            raise ValueError(
                "Could not resolve MTypeId value from {!r}".format(type_id)
            )
        return int(match.group(0), 0)


def normalize_node_type_name(type_name):
    normalized = str(type_name or "").strip()
    if normalized.endswith(ABSTRACT_SUFFIX):
        return normalized[: -len(ABSTRACT_SUFFIX)].strip()
    return normalized


def node_type_name(node_class):
    type_name = getattr(node_class, "typeName", None)
    if callable(type_name):
        try:
            return str(type_name())
        except Exception:
            pass
    if type_name:
        return str(type_name)

    name = getattr(node_class, "name", None)
    if callable(name):
        try:
            return str(name())
        except Exception:
            pass
    if name:
        return str(name)

    return "<unknown>"


def node_plugin_name(node_class):
    plugin_name = getattr(node_class, "pluginName", None)
    if callable(plugin_name):
        try:
            plugin_name = plugin_name()
        except Exception:
            plugin_name = ""
    return str(plugin_name or "").strip()


def node_classification(node_class):
    # type: (object) -> str
    classification = getattr(node_class, "classification", None)
    if callable(classification):
        try:
            classification = classification()
        except Exception:
            classification = ""

    if not classification:
        classification = getattr(node_class, "classificationString", "")
        if callable(classification):
            try:
                classification = classification()
            except Exception:
                classification = ""

    return to_text(classification)


def collect_registered_type_ids():
    """Collect unique type IDs from currently registered node type names."""
    seen_names = set()
    collected = OrderedDict()
    skipped_nodes = set(DANGEROUS_NODES) | USER_SKIPPED_NODES

    for raw_name in cmds.allNodeTypes() or []:
        type_name = normalize_node_type_name(raw_name)
        if not type_name or type_name in seen_names:
            continue
        if type_name in skipped_nodes:
            print("Skipping node type '{}'".format(type_name))
            continue

        seen_names.add(type_name)

        try:
            node_class = om2.MNodeClass(type_name)
        except RuntimeError:
            continue

        if not node_class:
            continue

        try:
            raw_id = mtypeid_to_int(node_class.typeId)
        except (TypeError, ValueError) as exc:
            print("Failed to resolve type id for {}: {}".format(type_name, exc))
            continue

        if raw_id not in collected:
            collected[raw_id] = type_name

        # print("Collected node id {} for type name '{}'".format(hex(raw_id), type_name))

    return sorted(collected)


def dump_registered_nodes_using_multiprocessing():
    import multiprocessing as mp

    load_plugins()
    type_ids = collect_registered_type_ids()
    print("Collected {} registered MTypeId values.".format(len(type_ids)))
    if not type_ids:
        print("No registered node types found.")
        manifest_nodes = []
        failures = []
        write_dump_artifacts(manifest_nodes, failures)
        print_processing_summary(0, manifest_nodes, failures)
        return

    process_count = 1  # mp.cpu_count()
    po = mp.Pool(process_count)
    po.map(initialize_process, range(process_count))
    results = po.map(dump_node_by_id, type_ids)
    po.close()
    po.join()

    manifest_nodes = []
    failures = []
    for result in results:
        collapse_result(result, manifest_nodes, failures)
    write_dump_artifacts(manifest_nodes, failures)
    print_processing_summary(len(type_ids), manifest_nodes, failures)

    print("... done processing")


def dump_registered_nodes_serial():
    load_plugins()
    type_ids = collect_registered_type_ids()
    print("Collected {} registered MTypeId values.".format(len(type_ids)))
    if not type_ids:
        print("No registered node types found.")
        manifest_nodes = []
        failures = []
        write_dump_artifacts(manifest_nodes, failures)
        print_processing_summary(0, manifest_nodes, failures)
        return

    manifest_nodes = []
    failures = []
    for raw_id in type_ids:
        try:
            result = dump_node_by_id(raw_id)
            collapse_result(result, manifest_nodes, failures)
        except Exception as exc:
            print(
                "Skipping {} due to unexpected error: {}".format(hex(raw_id), exc)
            )
            failures.append(
                make_failure_record(raw_id, "", "unexpected", exc)
            )

    write_dump_artifacts(manifest_nodes, failures)
    print_processing_summary(len(type_ids), manifest_nodes, failures)

    print("... done processing")


##############################################################################
def dump_node_by_id(raw_id):

    type_id = om2.MTypeId(raw_id)
    node_name = "<unknown>"
    try:
        node_class = om2.MNodeClass(type_id)
    except RuntimeError as exc:
        print("Failed to resolve node class for {}: {}".format(hex(raw_id), exc))
        return {"failure": make_failure_record(raw_id, node_name, "resolveNodeClass", exc)}

    if not node_class:
        return {
            "failure": make_failure_record(
                raw_id, node_name, "resolveNodeClass", "node class not found"
            )
        }

    node_name = node_type_name(node_class)

    try:
        attribute_count = node_class.attributeCount
    except RuntimeError as exc:
        print("Failed to get attribute count for {}: {}".format(hex(raw_id), exc))
        return {"failure": make_failure_record(raw_id, node_name, "attributeCount", exc)}

    obj = None
    dpn = None
    if CREATE_NODE_INSTANCE:
        typ = om2.MFnDependencyNode()
        try:
            obj = typ.create(type_id, "test")
        except RuntimeError as exc:
            print(
                "Failed to create node for {} {}".format(
                    hex(raw_id), node_type_name(node_class)
                )
            )
            return {"failure": make_failure_record(raw_id, node_name, "createNode", exc)}
        dpn = om2.MFnDependencyNode(obj)

    attributes = {}
    for num in range(attribute_count):
        try:
            attr_obj = dpn.attribute(num) if dpn else node_class.attribute(num)
            a = om2.MFnAttribute(attr_obj)
        except RuntimeError:
            print(
                "Failed to access attribute {} of node {} {}".format(
                    num, hex(raw_id), node_type_name(node_class)
                )
            )
            continue

        try:
            k, v = inspect_attribute(a, node_obj=obj)
        except RuntimeError as exc:
            print(
                "Failed to inspect attribute {} of node {} {}: {}".format(
                    num, hex(raw_id), node_type_name(node_class), exc
                )
            )
            continue

        attributes[k] = v

    # organize attributes in preparation for writing
    attributes = OrderedDict(sorted(attributes.items()))
    attributes = consolidate_kids(attributes)
    appear_in_cbox_attrs = OrderedDict(
        (k, v) for (k, v) in attributes.items() if v["is_appear_cbox"]
    )
    extern_attrs = OrderedDict(
        (k, v)
        for (k, v) in attributes.items()
        if not v["is_internal"] and not v["is_appear_cbox"] and not v["is_hidden"]
    )
    extern_hidden = OrderedDict(
        (k, v)
        for (k, v) in attributes.items()
        if not v["is_internal"] and not v["is_appear_cbox"] and v["is_hidden"]
    )
    internal_attrs = OrderedDict(
        (k, v) for (k, v) in attributes.items() if v["is_internal"]
    )

    try:
        plugin_name = (
            dpn.pluginName if dpn else node_plugin_name(node_class)
        ) or "_default"
    except RuntimeError as exc:
        print("Failed to resolve plugin name for {}: {}".format(hex(raw_id), exc))
        plugin_name = "_default"

    try:
        write_rst(
            plugin_name,
            raw_id,
            node_class,
            attributes,
            appear_in_cbox_attrs,
            extern_attrs,
            extern_hidden,
            internal_attrs,
        )
    except Exception as exc:
        print("Failed to write rst for {} {}: {}".format(hex(raw_id), node_name, exc))
        return {"failure": make_failure_record(raw_id, node_name, "writeRst", exc)}

    if obj is not None:
        try:
            dg_mod = om2.MDGModifier()
            dg_mod.deleteNode(obj)
            dg_mod.doIt()
        except RuntimeError as exc:
            # Some plug-ins can fail deletion in standalone; do not abort full dump.
            print("Failed to delete temporary node {}: {}".format(hex(raw_id), exc))
            try:
                cmds.delete(dpn.name())
            except Exception:
                pass

        del obj
        del dpn

    manifest_node = build_manifest_node(
        raw_id=raw_id,
        node_name=node_name,
        plugin_name=plugin_name,
        classification=node_classification(node_class),
        attribute_count=attribute_count,
        attributes=attributes,
    )

    return {"manifest_node": manifest_node}


def inspect_attribute(attr, node_obj=None):
    ''' inspect given attribute and return its longname and information as dict '''

    plg = None
    if node_obj is not None:
        try:
            plg = om2.MPlug(node_obj, attr.object())
        except RuntimeError:
            pass

    name_long = attr.name
    name_short = attr.shortName
    add_cmd = attr.getAddAttrCmd(True)
    # info = plg.info  # never use
    # set_cmd = plg.getSetAttrCmds(om2.MPlug.kAll, True)  # never use

    flags = []
    kwargs = parse_mel_cmd_args(add_cmd)
    attr_type = kwargs.get("attributeType", "")

    is_appear_cbox = attr.channelBox
    is_extension = attr.extension
    is_readable = attr.readable
    is_writable = attr.writable
    is_connectable = attr.connectable
    is_hidden = attr.hidden
    is_array = attr.array
    is_storable = attr.storable
    is_keyable = attr.keyable

    is_internal = attr.internal

    # if keyable, appear in channel box ref: http://download.autodesk.com/us/maya/2011help/API/class_m_fn_attribute.html#ea44dd2a0f7d68a3e47f713b7732d05c
    if is_keyable:
        is_appear_cbox = True

    if is_extension:
        flags.append("extension")
    if is_connectable:
        flags.append("connectable")
        if is_writable:
            flags.append("in")
        if is_readable:
            flags.append("out")

    if is_storable:
        flags.append("storable")
    if is_array:
        flags.append("array")
    if is_keyable:
        flags.append("keyable")
    if is_hidden:
        flags.append("hidden")

    parent = None
    try:
        parent_obj = attr.parent
        if hasattr(parent_obj, "isNull") and not parent_obj.isNull():
            parent = om2.MFnAttribute(parent_obj).name
    except RuntimeError:
        pass

    val = kwargs.get("defaultValue", "")
    if plg is not None:
        val = get_plug_val(attr_type, plg, kwargs)
    def_val = kwargs.get("defaultValue", None)
    min_val = kwargs.get("minValue", None)
    max_val = kwargs.get("maxValue", None)
    enum_val = kwargs.get("enumName", "")

    flags = normalize_flags(flags)
    val = normalize_scalar(val)
    def_val = normalize_scalar(def_val)
    min_val = normalize_scalar(min_val)
    max_val = normalize_scalar(max_val)
    enum_val = normalize_scalar(enum_val)
    if "enum" in normalize_scalar(attr_type).lower() and not def_val and val:
        def_val = val
    enum_items = parse_enum_items(enum_val, def_val)

    value = {
        "short_name": name_short,
        "type": normalize_scalar(attr_type),
        "parent": parent,
        "add_cmd": add_cmd,
        "value": val,
        "default_value": def_val,
        "min_value": min_val,
        "max_value": max_val,
        "enum": enum_val,
        "flags": flags,
        "display_value": display_or_dash(val),
        "display_default": display_or_dash(def_val),
        "display_minmax": format_minmax_display(min_val, max_val),
        "display_flags": ", ".join(flags) if flags else "-",
        "display_type": display_or_dash(normalize_scalar(attr_type)),
        "display_enum": enum_val.replace(":", ", ") if enum_val else "",
        "display_enum_items": enum_items,
        "is_internal": is_internal,
        "is_appear_cbox": is_appear_cbox,
        "is_hidden": is_hidden,
        "kids": {},
    }
    return name_long, value


def get_plug_val(attr_type, plg, kwargs):
    val = ""
    try:
        if "bool" in attr_type:
            val = plg.asBool()
        elif "byte" in attr_type:
            val = plg.asBool()
        elif "double" in attr_type:
            val = plg.asDouble()
        elif "double3" in attr_type:
            val = plg.asMDataHandle().asDouble3()
        elif "doubleAngle" in attr_type:
            val = plg.asMAngle()
        elif "doubleLinear" in attr_type:
            val = plg.asMDistance()
        elif "float" in attr_type:
            val = plg.asFloat()
        elif "float3" in attr_type:
            val = plg.asMDataHandle().asFloat3()
        elif "long" in attr_type:
            val = plg.asFloat()
        elif "message" in attr_type:
            val = plg.asString()
        elif "short" in attr_type:
            val = plg.asShort()
        elif "time" in attr_type:
            val = plg.asMTime().asUnits(om2.MTime.kSeconds)
        elif "enum" in attr_type:
            val = plg.asShort()
        # elif 'compound'     in attr_type: val = plg.asMDataHandle()

    except RuntimeError:
        pass

    return val


def parse_mel_cmd_args(cmd):
    ''' return kwargs as dict'''

    results = {}
    exp = re.compile(" -")
    for a in exp.split(cmd):
        parts = a.split(" ")
        k = parts[0]
        v = " ".join(parts[1:]) or "true"
        v = v.lstrip('"').rstrip(';').rstrip('"')

        results[k] = v

    return results


def consolidate_kids(arr):

    results = OrderedDict()
    for k, v in arr.items():

        if v["parent"]:
            parent_name = v["parent"]
            parent_value = arr.get(parent_name)
            if parent_value is None:
                results[k] = v
                continue

            if parent_name not in results:
                results[parent_name] = parent_value

            results[parent_name]["kids"][k] = v
            if v["is_appear_cbox"]:
                # apper parent in channel box, if kids visible
                results[parent_name]["is_appear_cbox"] = True

        results[k] = v

    # return filter(lambda x: not x['parent'], results)
    return OrderedDict((k, v) for k, v in results.items() if not v["parent"])


def flatten_attribute_tree(attributes):
    # type: (OrderedDict) -> list
    flattened = []

    def _walk(items):
        # type: (OrderedDict) -> None
        for name, info in items.items():
            flattened.append((name, info))
            kids = info.get("kids") or OrderedDict()
            if kids:
                _walk(kids)

    _walk(attributes)
    return flattened


def build_manifest_attribute(name, info):
    # type: (str, dict) -> dict
    flags = normalize_flags(info.get("flags", []))
    return {
        "name": to_text(name),
        "shortName": to_text(info.get("short_name")),
        "type": normalize_scalar(info.get("type")),
        "value": normalize_scalar(info.get("value")),
        "default": normalize_scalar(info.get("default_value")),
        "min": normalize_scalar(info.get("min_value")),
        "max": normalize_scalar(info.get("max_value")),
        "enum": normalize_scalar(info.get("enum")),
        "parent": normalize_scalar(info.get("parent")),
        "flags": flags,
    }


def build_manifest_node(
    raw_id, node_name, plugin_name, classification, attribute_count, attributes
):
    # type: (int, str, str, str, int, OrderedDict) -> dict
    flattened = flatten_attribute_tree(attributes)
    manifest_attrs = []
    for name, info in flattened:
        manifest_attrs.append(build_manifest_attribute(name, info))

    manifest_attrs = sorted(manifest_attrs, key=lambda item: item["name"].lower())
    return {
        "typeId": hex(raw_id),
        "typeName": to_text(node_name) or "<unknown>",
        "plugin": normalize_plugin_name(plugin_name),
        "classification": normalize_scalar(classification),
        "attributeCount": int(attribute_count),
        "attributes": manifest_attrs,
    }


def write_rst(
    plugin_name,
    raw_id,
    node_class,
    attributes,
    appear_in_cbox_attrs,
    extern_attrs,
    extern_hidden,
    internal_attrs,
):
    plugin_basename = os.path.basename(plugin_name)
    plugin_dir = os.path.join(output_dir, plugin_basename)
    if not os.path.isdir(plugin_dir):
        os.makedirs(plugin_dir)

    output_file = os.path.join(plugin_dir, "{}.rst".format(hex(raw_id)))
    dat = apply_rst_template(
        raw_id,
        node_class,
        attributes,
        appear_in_cbox_attrs,
        internal_attrs,
        extern_attrs,
        extern_hidden=extern_hidden,
        plugin=plugin_basename,
        maya_docs_year=MAYA_DOCS_YEAR,
        maya_docs_base_url=MAYA_DOCS_BASE_URL,
    )
    with io.open(output_file, "w", encoding="utf-8") as fp:
        fp.write(dat)
    # json.dump(attributes, fp)


def apply_rst_template(
    node_id,
    node,
    attrs,
    appear_in_cbox_attrs,
    internal_attrs,
    extern_attrs,
    extern_hidden,
    **kwargs
):
    results = tmpl.render(
        id=hex(node_id),
        node=node,
        attributes=attrs,
        appear_in_cbox_attrs=appear_in_cbox_attrs,
        internal_attrs=internal_attrs,
        extern_attrs=extern_attrs,
        extern_hidden=extern_hidden,
        **kwargs
    )

    return results


def initialize_process(*args):
    load_plugins()


def maybe_force_os_exit(exit_code):
    # type: (int) -> None
    if sys.version_info[0] >= 3:
        return
    if not FORCE_OS_EXIT_ON_PY2:
        return

    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass

    os._exit(exit_code)


def load_plugins():
    allow_unsafe = os.getenv("DUMP_ALLOW_UNSAFE_PLUGINS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    def is_dangerous_plugin(stem):
        if stem in DANGEROUS_PLUGINS:
            return True
        lower = stem.lower()
        return any(keyword in lower for keyword in DANGEROUS_PLUGIN_KEYWORDS)

    plugin_paths = []
    for p in os.getenv("MAYA_PLUG_IN_PATH", "").split(os.pathsep):
        if p:
            plugin_paths.extend(glob.glob(os.path.join(p, "*.mll")))
            plugin_paths.extend(glob.glob(os.path.join(p, "*.py")))

    plugin_names = []
    for path in plugin_paths:
        stem = os.path.splitext(os.path.basename(path))[0]
        name = os.path.basename(path)
        if not allow_unsafe and is_dangerous_plugin(stem):
            print("Skipping dangerous plugin '{}'".format(name))
            continue
        plugin_names.append(name)
    plugin_names = sorted(set(plugin_names))

    def _l(name):
        try:
            cmds.loadPlugin(name)
        except Exception:
            pass

    for n in plugin_names:
        _l(n)


# shortcut
known_idx = [

    0x345dad01,
    0x346dad01,
    0x41424141,
    0x41424146,
    0x41424149,
    0x4142414c,
    0x41424153,
    0x4142424f,
    0x41424641,
    0x4142464c,
    0x4142494f,
    0x41424c32,
    0x41424c45,
    0x41424c57,
    0x41424e41,
    0x41424e42,
    0x41424e44,
    0x41424e45,
    0x41424e52,
    0x41424e53,
    0x41425449,
    0x41444d4e,
    0x4144534d,
    0x4147444e,
    0x41494e44,
    0x41494e53,
    0x41494e54,
    0x414d424c,
    0x414e4c52,
    0x414e4e53,
    0x4150424c,
    0x4150524d,
    0x41524c54,
    0x41534259,
    0x41544854,
    0x41554449,
    0x42414b45,
    0x42435256,
    0x42444454,
    0x424c4454,
    0x424c4456,
    0x42525348,
    0x42535748,
    0x42544e52,
    0x43324744,
    0x43424153,
    0x43434846,
    0x43475348,
    0x43484152,
    0x43484345,
    0x43484f4f,
    0x434c4950,
    0x434c504e,
    0x434d4150,
    0x434e4d50,
    0x434e5241,
    0x434e524c,
    0x434e524d,
    0x434f4241,
    0x434f4c50,
    0x434f4e53,
    0x434f4e54,
    0x43504353,
    0x43504f4d,
    0x43505553,
    0x43524353,
    0x43524541,
    0x43525553,
    0x43534348,
    0x43535353,
    0x4354524b,
    0x4441444c,
    0x44414743,
    0x4441474e,
    0x44414d43,
    0x44414d50,
    0x44414d58,
    0x44425453,
    0x4443414d,
    0x44434156,
    0x44434f4e,
    0x44435054,
    0x44444254,
    0x44444d4e,
    0x44445343,
    0x44454354,
    0x4445464c,
    0x44455850,
    0x4446434e,
    0x4446494b,
    0x44464d4c,
    0x44474649,
    0x44474d43,
    0x44474e43,
    0x4447504c,
    0x44485056,
    0x4449504c,
    0x4449524c,
    0x444c4154,
    0x444c4353,
    0x444c4354,
    0x444c4d53,
    0x444d444c,
    0x444d5348,
    0x444d5449,
    0x444d544d,
    0x444e4332,
    0x444e5243,
    0x444f4644,
    0x444f5243,
    0x44504152,
    0x4450484d,
    0x44504c4d,
    0x44504d4d,
    0x44505043,
    0x4450534d,
    0x44505443,
    0x44505643,
    0x44524e4c,
    0x44525452,
    0x4452554c,
    0x44534343,
    0x44534850,
    0x44534b43,
    0x44534d43,
    0x4453504c,
    0x44544332,
    0x44544d55,
    0x44544e43,
    0x44554e54,
    0x4455544d,
    0x4457414d,
    0x44574746,
    0x454d5444,
    0x454e4d50,
    0x454e5459,
    0x454e5646,
    0x46424153,
    0x4642454c,
    0x4642464d,
    0x46424c53,
    0x4642554c,
    0x46434348,
    0x46434c48,
    0x46434c53,
    0x46444244,
    0x46444646,
    0x4644464c,
    0x4644534e,
    0x46445351,
    0x46445457,
    0x46445756,
    0x46454d49,
    0x46464442,
    0x46464644,
    0x46475549,
    0x46494258,
    0x4649434f,
    0x46494c54,
    0x46495350,
    0x464a4346,
    0x464a434c,
    0x464c4154,
    0x464c4f57,
    0x464c5443,
    0x464c5445,
    0x464c5452,
    0x464c5453,
    0x464c5454,
    0x464c5458,
    0x464c5549,
    0x464c5848,
    0x464d5054,
    0x464e4c44,
    0x46504f53,
    0x4650524e,
    # 0x4653434c,
    # 0x46534350,
    # 0x46534c4d,
    # 0x46534d50,
    0x46535348,
    0x4653534c,
    0x46574952,
    0x46575250,
    0x4742494e,
    0x4743434c,
    0x47504944,
    0x47504c4e,
    0x47505253,
    0x47505351,
    0x47525050,
    0x47534850,
    0x48435256,
    0x48454c49,
    0x4846434d,
    0x48474e44,
    0x48495353,
    0x4850494e,
    0x48525247,
    0x48535953,
    0x48544e31,
    0x48544e32,
    0x48544e33,
    0x48575247,
    0x4857524d,
    0x4859504c,
    0x48595052,
    0x494b4546,
    0x4a474446,
    0x4a4f494e,

    0x4a54494b,
    0x4b454646,
    0x4b46524d,
    0x4b475250,
    0x4b48444c,
    0x4b484948,
    0x4b48494b,
    0x4b4d4353,
    0x4b504153,
    0x4b525053,
    0x4b534353,
    0x4b535053,
    0x4b53564c,
    0x4b535953,
    0x4c4c5354,
    0x4c4d4f44,
    0x4c4f4354,
    0x4c4f4447,
    0x4c4f4454,
    0x4c534e45,
    0x4c544d50,
    0x4c595253,
    0x4c595254,
    0x4d424454,
    0x4d424850,
    0x4d454d42,
    0x4d495343,
    0x4d4f5348,
    0x4d4f5452,
    0x4d505448,
    0x4d554c4c,
    0x4d555445,
    0x4d6f5576,
    0x4e324341,
    0x4e334341,
    0x4e414254,
    0x4e414352,
    0x4e414c43,
    0x4e414c53,
    0x4e414d42,
    0x4e414e50,
    0x4e415350,
    0x4e415443,
    0x4e415453,
    0x4e424153,
    0x4e424253,
    0x4e424c53,
    0x4e424c54,
    0x4e424e43,
    0x4e424e44,
    0x4e424f4c,
    0x4e425346,
    0x4e425356,
    0x4e425647,
    0x4e42564c,
    0x4e434152,
    0x4e434349,
    0x4e434355,
    0x4e43464d,
    0x4e434653,
    0x4e43494e,
    0x4e434c4f,
    0x4e434d43,
    0x4e434d45,
    0x4e434d50,
    0x4e434e45,
    0x4e435053,
    0x4e435243,
    0x4e435245,
    0x4e435256,
    0x4e435342,
    0x4e435343,
    0x4e435349,
    0x4e435355,
    0x4e435542,
    0x4e435647,
    0x4e435653,
    0x4e43594c,
    0x4e444253,
    0x4e445348,
    0x4e445443,
    0x4e445453,
    0x4e455348,
    0x4e455843,
    0x4e455852,
    0x4e455853,
    0x4e455854,
    0x4e464352,
    0x4e464653,
    0x4e465443,
    0x4e475354,
    0x4e475647,
    0x4e484450,
    0x4e494b43,
    0x4e494b53,
    0x4e495346,
    0x4e4c534d,
    0x4e4d4253,
    # 0x4e4d4943,
    0x4e4d5647,
    0x4e4f4353,
    0x4e4f4355,
    0x4e4f4445,
    0x4e4f5355,
    0x4e504152,
    0x4e504349,
    0x4e504352,
    0x4e504c4e,
    0x4e504c54,
    0x4e504f43,
    0x4e50524d,
    0x4e505349,
    0x4e50544e,
    0x4e524243,
    0x4e524246,
    0x4e524253,
    0x4e524352,
    0x4e524744,
    0x4e525053,
    0x4e525442,
    0x4e525643,
    0x4e52564c,
    0x4e525653,
    0x4e534243,
    0x4e534253,
    0x4e534352,
    0x4e53494e,
    0x4e534b4e,
    0x4e534d43,
    0x4e535048,
    0x4e535152,
    0x4e535153,
    0x4e535246,
    0x4e535348,
    0x4e535352,
    0x4e535443,
    0x4e53544e,
    0x4e535453,
    0x4e535647,
    0x4e535953,
    0x4e544553,
    0x4e544f52,
    0x4e54524d,
    0x4e545742,
    0x4e54574b,
    0x4e545843,
    0x4e555452,
    0x4f425354,
    0x4f435050,
    0x4f464154,
    0x4f464c54,
    0x4f4b464c,
    0x4f4d464c,
    0x4f4e464c,
    0x4f504658,
    0x4f52464c,
    0x4f524744,
    0x4f52544d,
    0x4f53464c,
    0x4f54464c,
    0x502e2e2e,
    0x50414d41,
    0x50414f4d,
    0x50415050,
    0x50415056,
    0x50415453,
    0x50415550,
    0x50415656,
    0x50424353,
    0x50424f50,
    0x50425245,
    0x50425632,
    0x5042564c,
    0x50432e2e,
    0x5043434d,
    0x50434353,
    0x5043444c,
    0x50434849,
    0x50434c44,
    0x50434c4f,
    0x50434d41,
    0x50434d4f,
    0x50434d51,
    0x50434f45,
    0x50434f46,
    0x50434f4e,
    0x50435056,
    0x50435245,
    0x50435253,
    0x50435345,
    0x50435441,
    0x5043544c,
    0x5043544d,
    0x50435454,
    0x50435455,
    0x50435541,
    0x50435542,
    0x5043554c,
    0x50435554,
    0x50435555,
    0x50435556,
    0x50435642,
    0x5043594c,
    0x50435950,
    0x50444545,
    0x50444546,
    0x50444556,
    0x50445545,
    0x50454d43,
    0x50455845,
    0x50455846,
    0x5045584d,
    0x50455856,
    0x50464745,
    0x50464841,
    0x50464c45,
    0x5046544f,
    0x50465556,
    0x50484645,
    0x50494d41,
    0x504c4e45,
    0x504c5556,
    0x504d4143,
    0x504d4144,
    0x504d4153,
    0x504d4356,
    0x504d4457,
    0x504d4545,
    0x504d4546,
    0x504d4553,
    0x504d4655,
    0x504d4752,
    0x504d4755,
    0x504d4952,
    0x504d4f44,
    0x504d4f45,
    0x504d4f46,
    0x504d4f56,
    0x504d5556,
    0x504d5645,
    0x504d564d,
    0x504e4f52,
    0x504e5056,
    0x504e5556,
    0x504f4954,
    0x504f534d,
    0x504f5556,
    0x50504354,
    0x50504356,
    0x50504950,
    0x50504c50,
    0x5050504b,
    0x50505249,
    0x5050524d,
    0x5050524f,
    0x50505354,
    0x50505952,
    0x50515541,
    0x50524544,
    0x5052544e,
    0x5053434d,
    0x50534453,
    0x50534454,
    0x50534544,
    0x50534546,
    0x5053454d,
    0x50534550,
    0x5053494e,
    0x50534d46,
    0x50534d50,
    0x50534d54,
    0x50534f45,
    0x50535048,
    0x5053504c,
    0x50535050,
    0x50535051,
    0x50535052,
    0x50535442,
    0x50535545,
    0x50535546,
    0x50535645,
    0x50535745,
    0x50544356,
    0x5054464d,
    0x50544652,
    0x50544d41,
    0x50544f52,
    0x50545249,
    0x50545556,
    0x5054574b,
    0x50554e49,
    0x50555652,
    0x50574643,
    0x50584d47,
    0x52414e49,
    0x52424c32,
    0x52424c4e,
    0x52425533,
    0x5242554d,
    0x52434953,
    0x52434c33,
    0x52434e44,
    0x52434f4e,
    0x52435441,
    0x5243544c,
    0x52435454,
    0x52435455,
    0x5244474c,
    0x52444d4e,
    0x52445348,
    0x5244534c,
    0x5244544c,
    0x5245424c,
    0x52454342,
    0x52454344,
    0x52454348,
    0x52454643,
    0x52454647,
    0x5245464e,
    0x52454656,
    0x5245534b,
    0x52455350,
    0x5246424d,
    0x52464c43,
    0x52464f47,
    0x5247414d,
    0x52474c42,
    0x52483252,
    0x52485442,
    0x52485753,
    0x524c414d,
    0x524c494e,
    0x524c4c4b,
    0x524c534e,
    0x524c544e,
    0x524c554d,
    0x524d434c,
    0x524d4449,
    0x524d4643,
    0x524d4853,
    0x524d5458,
    0x524d564c,
    0x524e4258,
    0x524e434f,
    0x524e444c,
    0x524e4953,
    0x524e4c4d,
    0x524e5053,
    0x524e5350,
    0x524e5447,
    0x524f5053,
    0x52504845,
    0x5250484f,
    0x52504c32,
    0x52504c44,
    0x52504d41,
    0x5250524a,
    0x52505353,
    0x52515541,
    0x52523248,
    0x52524354,
    0x52524e47,
    0x52525053,
    0x52525653,
    0x52533430,
    0x52533630,
    0x52534356,
    0x5253494e,
    0x52534c55,
    0x52535348,
    0x52543246,
    0x52544255,
    0x52544344,
    0x52544348,
    0x5254434c,
    0x52544633,
    0x52544654,
    0x52544744,
    0x52544752,
    0x52544c45,
    0x52544d33,
    0x52544d41,
    0x52544d52,
    0x52544d54,
    0x52544d56,
    0x52544e33,
    0x52544f43,
    0x52545241,
    0x5254524b,
    0x5254534e,
    0x52545354,
    0x52545633,
    0x52545741,
    0x52545744,
    0x52545832,
    0x52545833,
    0x52545845,
    0x52564543,
    0x52564647,
    0x52565348,
    0x532e2e2e,
    0x5341434d,
    0x53415459,
    0x53415550,
    0x53424454,
    0x53434653,
    0x53434c50,
    0x53434c52,
    0x53434d50,
    0x53435250,
    0x53435345,
    0x53435346,
    0x53435459,
    0x53444d50,
    0x5344534e,
    0x53445350,
    0x53445353,
    0x5345464d,
    0x53484144,
    0x5348444e,
    0x5348474c,
    0x53484f54,
    0x53485045,
    0x53485242,
    0x534b4244,
    0x534b504e,
    0x534c4f50,
    0x534c5556,
    0x534d4143,
    0x534d4457,
    0x534d4541,
    0x534d4f44,
    0x534d5576,
    0x534e5054,
    0x534e5450,
    0x534e5453,
    0x534f4c49,
    0x53504c50,
    0x5350544c,
    0x53514d47,
    0x53514e43,
    0x53524341,
    0x53525646,
    0x5353454d,
    0x53534841,
    0x53534944,
    0x53534d4e,
    0x53535647,
    0x53544553,
    0x53544b47,
    0x53544e44,
    0x5354524b,
    0x53545556,
    0x5354574b,
    0x53565348,
    0x53574831,
    0x53574832,
    0x53574833,
    0x53574834,
    0x53575250,
    0x5442414b,
    0x5442444d,
    0x54444844,
    0x54444d32,
    0x5447454f,
    0x54494d45,
    0x54495741,
    0x544c4154,
    0x544c444d,
    0x544d534d,
    0x54524154,
    0x54534d4d,
    0x5453524d,
    0x5454444d,
    0x5454474f,
    0x54584446,
    0x54584b45,
    0x54584c54,
    0x55325041,
    0x5532524f,
    0x55325343,
    0x5532534e,
    0x5532544d,
    0x55325452,
    0x55415454,
    0x55415841,
    0x55424e44,
    0x55434350,
    0x5543534d,
    0x55435354,
    0x5544414d,
    0x55444246,
    0x5544454d,
    0x5544464d,
    0x55444e4d,
    0x5544534d,
    0x5544544d,
    0x55464c52,
    0x55465054,
    0x55494b52,
    0x55494b53,
    0x554d3243,
    0x554d3244,
    0x554d4143,
    0x554d4144,
    0x554d4152,
    0x554d4243,
    0x554d4244,
    0x554d424c,
    0x554d4250,
    0x554d4254,
    0x554d4256,
    0x554d4341,
    0x554d4343,
    0x554d4345,
    0x554d4349,
    0x554d434c,
    0x554d434f,
    0x554d4350,
    0x554d4353,
    0x554d4354,
    0x554d4355,
    0x554d4356,
    0x554d4359,
    0x554d4446,
    0x554d444d,
    0x554d4452,
    0x554d4543,
    0x554d4550,
    0x554d4553,
    0x554d4558,
    0x554d4650,
    0x554d4653,
    0x554d4655,
    0x554d474c,
    0x554d4953,
    0x554d4958,
    0x554d4a43,
    0x554d4a54,
    0x554d4c4e,
    0x554d4c54,
    0x554d4d41,
    0x554d4d4d,
    0x554d4d50,
    0x554d4f43,
    0x554d4f53,
    0x554d5043,
    0x554d504c,
    0x554d504d,
    0x554d5050,
    0x554d5053,
    0x554d5054,
    0x554d5055,
    0x554d5241,
    0x554d5243,
    0x554d5244,
    0x554d524c,
    0x554d524f,
    0x554d5250,
    0x554d5252,
    0x554d5253,
    0x554d5256,
    0x554d5343,
    0x554d5345,
    0x554d534c,
    0x554d534d,
    0x554d5350,
    0x554d5351,
    0x554d5353,
    0x554d5442,
    0x554d5444,
    0x554d5445,
    0x554d5447,
    0x554d544c,
    0x554d544d,
    0x554d5452,
    0x554d5458,
    0x554d5556,
    0x554d5657,
    0x554d5846,
    0x554e4b44,
    0x554e4b4e,
    0x554e4b54,
    0x554f4353,
    0x5550324d,
    0x55504d4d,
    0x55504d50,
    0x55504d51,
    0x5550504d,
    0x5550524d,
    0x55505331,
    0x5550544d,
    0x5550554d,
    0x5550564d,
    0x5551504c,
    0x55534247,
    0x5553494e,
    0x55534c4d,
    0x55534d51,
    0x5553504d,
    0x55535148,
    0x5553524d,
    0x5554434d,
    0x5554494d,
    0x55544f4c,
    0x55545041,
    0x55545043,
    0x55545053,
    0x5554544d,
    0x55545749,
    0x5556324d,
    0x55564348,
    0x55564e4d,
    0x5556544d,
    0x55574156,
    0x5557444d,
    0x5642414b,
    0x56424e42,
    0x564f4c4c,
    0x56545247,
    0x5657434d,
    0x57544342,
    0x57544442,
    0x57544642,
    0x57544c42,
    0x57545642,
    0x58000010,
    0x58000013,
    0x58000015,
    0x58000016,
    0x58000020,
    0x58000021,
    0x58000022,
    0x58000023,
    0x58000024,
    0x58000025,
    0x58000026,
    0x58000030,
    0x58000080,
    0x58000081,
    0x58000082,
    0x58000083,
    0x58000084,
    0x58000085,
    0x58000090,
    0x58000091,
    0x58000092,
    0x580000a0,
    0x580000a1,
    0x580000c4,
    0x58000300,
    0x58000301,
    0x58000302,
    0x58000303,
    0x58000305,
    0x58000306,
    0x58000307,
    0x58000308,
    0x58000309,
    0x5800030a,
    0x5800030b,
    0x5800030c,
    0x5800030d,
    0x5800030e,
    0x5800030f,
    0x58000310,
    0x58000311,
    0x58000314,
    0x58000318,
    0x58000319,
    0x5800031a,
    0x58000322,
    0x58000333,
    0x58000336,
    0x58000337,
    0x5800034b,
    0x58000400,
    0x58000800,
    0x58000801,
    0x58000802,
    0x58000804,
    0x58000806,
    0x58000809,
    0x5800080b,
    0x5800080d,
    0x5800080f,
    0x58000810,
    0x5846524d,
    0x584f4646,
    0x59414952,
    0x59417578,
    0x59434f4c,
    0x59435354,
    0x5943544c,
    0x5944474c,
    0x59445247,
    0x59454d49,
    # 0x59464c44,
    # 0x5947434f,
    # 0x59474354,
    # 0x59475241,
    0x59484c44,
    0x59485244,
    0x594e4557,
    0x594e5354,
    0x59504152,
    0x59524144,
    0x59524744,
    0x59534c56,
    0x59535052,
    0x59545552,
    0x59554e49,
    0x59564f52,
    0x59565846,
    0x636c6476

]


def dump_sigle_id(node_id):
    load_plugins()
    dump_node_by_id(node_id)


def dump_indice(indice):
    load_plugins()
    for node_id in indice:
        dump_node_by_id(node_id)


def dump_id_range_using_multiprocessing():

    import multiprocessing as mp
    process_count = 1  # mp.cpu_count()
    po = mp.Pool(process_count)
    po.map(initialize_process, range(process_count))

    start = 0x30000000
    steps = 0x00001000
    end = 0x90000001

    while start < end:
        res = po.map_async(dump_node_by_id, range(start, start + steps))

        # wait a moment as the main process eat up huge memory
        # when runnig continuously
        if len(po._cache) > 1e4:
            print(".", hex(start))
            res.wait()

        start = start + steps

    po.close()
    po.join()

    print('... done processing')


if __name__ == "__main__":

    # --------------------------------------------------------
    # dump for given single index
    # --------------------------------------------------------
    # dump_sigle_id(0x5254434c)

    # ---------------------------------------------------------
    # dump for given indice
    # ---------------------------------------------------------
    # dump_indice(known_idx)
    # dump_indice([x for x in range(0x30000000, 0x345dad01)])

    # ---------------------------------------------------------
    # dump for id range using multiprocessing
    # ---------------------------------------------------------
    # dump_id_range_using_multiprocessing()

    # ---------------------------------------------------------
    # dump for registered node types (deterministic in-session set)
    # ---------------------------------------------------------
    _exit_code = 0
    try:
        dump_registered_nodes_serial()
        # dump_registered_nodes_using_multiprocessing()
    except Exception:
        traceback.print_exc()
        _exit_code = 1
    finally:
        maybe_force_os_exit(_exit_code)

    raise SystemExit(_exit_code)
