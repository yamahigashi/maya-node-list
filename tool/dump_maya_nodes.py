# -*- coding: utf-8 -*-
##############################################################################
# Dump maya node's MTypeId in batch mayapy.
#
# CAUTION: this may take very verey long time for execution
#          modify idx range on your needs.
##############################################################################
import os
import re
import traceback
from collections import OrderedDict as OrderedDict
from jinja2 import Environment, FileSystemLoader

import maya.standalone


try:
    maya.standalone.initialize(name='python')
except Exception as e:
    traceback.print_exc()
    print e


import maya.api.OpenMaya as om2
import maya.cmds as cmds


##############################################################################
output_dir = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    r'..\source\nodes')

template_dir = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    r'..\source\_templates')

env = Environment(loader=FileSystemLoader(template_dir, encoding='utf8'))
tmpl = env.get_template('node.tpl.rst')
# print r'{}\_templates'.format(template_dir)


##############################################################################
def dump_node_by_id(raw_id):
    try:
        id = om2.MTypeId(raw_id)
        nc = om2.MNodeClass(id)

        if nc:
            ac = nc.attributeCount
            # print nc.typeName, nc.classification, nc.attributeCount

        else:
            # print("nothing to inspect")
            return

        typ = om2.MFnDependencyNode()
        obj = typ.create(id, 'test')
        dpn = om2.MFnDependencyNode(obj)

        attributes = {}
        for num in xrange(ac):
            a = om2.MFnAttribute(dpn.attribute(num))
            k, v = inspect_attribute(dpn, a)
            attributes[k] = v

        # organize attributes in preparation for writing
        attributes = OrderedDict(sorted(attributes.items()))
        attributes = consolidate_kids(attributes)
        appear_in_cbox_attrs = OrderedDict((k, v) for (k, v) in attributes.iteritems() if v['is_appear_cbox'])
        extern_attrs = OrderedDict((k, v) for (k, v) in attributes.iteritems() if not v['is_internal'] and not v['is_appear_cbox'] and not v['is_hidden'])
        extern_hidden = OrderedDict((k, v) for (k, v) in attributes.iteritems() if not v['is_internal'] and not v['is_appear_cbox'] and v['is_hidden'])
        internal_attrs = OrderedDict((k, v) for (k, v) in attributes.iteritems() if v['is_internal'])

        plugin_name = dpn.pluginName or "_default"

        # import json
        # with open(r'{}\{}.json'.format(output_dir, hex(raw_id)), 'w') as fp:
        #     json.dump(attributes, fp)
        write_rst(plugin_name, raw_id, nc, attributes, appear_in_cbox_attrs,
                  extern_attrs, extern_hidden, internal_attrs)
        # print(hex(raw_id), 'done')

        dg_mod = om2.MDGModifier()
        dg_mod.deleteNode(obj)
        dg_mod.doIt()

        del obj
        del dpn

    except RuntimeError:
        return


def inspect_attribute(dpn, attr):
    ''' inspect given attribute and return its longname and information as dict '''

    plg = om2.MPlug(dpn.object(), attr.object())

    name_long = attr.name
    name_short = attr.shortName
    add_cmd = attr.getAddAttrCmd(True)
    # info = plg.info  # never use
    # set_cmd = plg.getSetAttrCmds(om2.MPlug.kAll, True)  # never use

    flags = []
    is_internal = False
    kwargs = parse_mel_cmd_args(add_cmd)
    attr_type = kwargs.get('attributeType', '')

    is_appear_cbox = attr.channelBox
    is_extension = attr.extension
    is_readable = attr.readable
    is_writable = attr.writable
    is_connectable = attr.connectable
    is_hidden = attr.hidden
    is_array = attr.array
    is_storable = attr.storable
    is_keyable = attr.keyable

    is_internal = bool(kwargs.get('internalSet', False))
    is_internal = attr.internal

    # if keyable, appear in channel box ref: http://download.autodesk.com/us/maya/2011help/API/class_m_fn_attribute.html#ea44dd2a0f7d68a3e47f713b7732d05c
    if is_keyable: is_appear_cbox = True

    if is_extension: flags.append("extension")
    if is_connectable:
        flags.append("connectable")
        if is_writable: flags.append("in")
        if is_readable: flags.append("out")

    if is_storable: flags.append("storable")
    if is_array: flags.append("array")
    if is_keyable: flags.append("keyable")
    if is_hidden: flags.append("hidden")

    parent = None
    if plg.isChild:
        parent = om2.MFnAttribute(attr.parent).name

    val = get_plug_val(attr_type, plg, kwargs)
    def_val = kwargs.get('defaultValue', None)
    min_val = kwargs.get('minValue', None)
    max_val = kwargs.get('maxValue', None)
    value = {
        'short_name': name_short,
        'type': attr_type,
        'parent': parent,
        'add_cmd': add_cmd,
        'value': val,
        'default_value': def_val or '',
        'min_value': min_val or '',
        'max_value': max_val or '',
        'flags': flags,
        'is_internal': is_internal,
        'is_appear_cbox': is_appear_cbox,
        'is_hidden': is_hidden,
        'kids': {}
    }
    return name_long, value


def get_plug_val(attr_type, plg, kwargs):
    val = ''
    try:
        if   'bool'         in attr_type: val = plg.asBool()
        elif 'byte'         in attr_type: val = plg.asBool()
        elif 'double'       in attr_type: val = plg.asDouble()
        elif 'double3'      in attr_type: val = plg.asMDataHandle().asDouble3()
        elif 'doubleAngle'  in attr_type: val = plg.asMAngle()
        elif 'doubleLinear' in attr_type: val = plg.asMDistance()
        elif 'float'        in attr_type: val = plg.asFloat()
        elif 'float3'       in attr_type: val = plg.asMDataHandle().asFloat3()
        elif 'long'         in attr_type: val = plg.asFloat()
        elif 'message'      in attr_type: val = plg.asString()
        elif 'short'        in attr_type: val = plg.asShort()
        elif 'time'         in attr_type: val = plg.asMTime().asUnits(om2.MTime.kSeconds)

        elif 'enum'         in attr_type: val = kwargs.get('enumName', '')
        # elif 'compound'     in attr_type: val = plg.asMDataHandle()

    except RuntimeError:
        pass

    return val


def parse_mel_cmd_args(cmd):
    ''' return kwargs as dict'''

    results = {}
    exp = re.compile(" -")
    for a in exp.split(cmd):
        k = a.split(" ")[0]
        v = " ".join(a.split(" ")[1:]) or u"true"
        v = v.lstrip('"').rstrip(';').rstrip('"')

        results[k] = v

    return results


def consolidate_kids(arr):

    results = OrderedDict()
    for k, v in arr.iteritems():

        if v['parent']:
            if v['parent'] not in results:
                results[v['parent']] = arr[v['parent']]

            results[v['parent']]['kids'][k] = v
            if v['is_appear_cbox']:
                # apper parent in channel box, if kids visible
                results[v['parent']]['is_appear_cbox'] = True

        results[k] = v

    # return filter(lambda x: not x['parent'], results)
    return OrderedDict((k, v) for k, v in results.items() if not v['parent'])


def write_rst(plugin_name, raw_id, node_class, attributes, appear_in_cbox_attrs,
              extern_attrs, extern_hidden, internal_attrs):

    d = r'{}\{}'.format(output_dir, os.path.basename(plugin_name))
    if not os.path.exists(d):
        os.makedirs(os.path.abspath(d))

    with open(r'{}\{}\{}.rst'.format(output_dir, os.path.basename(plugin_name), hex(raw_id)), 'w') as fp:
        dat = apply_rst_template(
            raw_id, node_class, attributes,
            appear_in_cbox_attrs, internal_attrs, extern_attrs, extern_hidden=extern_hidden,
            plugin=os.path.basename(plugin_name))
        fp.writelines(dat)
        # json.dump(attributes, fp)


def apply_rst_template(id, node, attrs, appear_in_cbox_attrs, internal_attrs, extern_attrs, extern_hidden, **kwargs):
    results = tmpl.render(
        id=hex(id), node=node, attributes=attrs, appear_in_cbox_attrs=appear_in_cbox_attrs,
        internal_attrs=internal_attrs, extern_attrs=extern_attrs, extern_hidden=extern_hidden, **kwargs)

    return results


def initialize_process(*args):
    load_plugins()


def load_plugins():

    default_plugins = [
        "cleanPerFaceAssignment.mll",
        "ddsFloatReader.mll",
        "autoLoader.mll",
        "rotateHelper.mll",
        "clearcoat.mll",
        "ArubaTessellator.mll",
        "nearestPointOnMesh.mll",
        "ik2Bsolver.mll",
        "objExport.mll",
        "dgProfiler.mll",
        "DirectConnect.mll",
        "quatNodes.mll",
        "hlslShader.mll",
        "matrixNodes.mll",
        "ikSpringSolver.mll",
        "animImportExport.mll",
        "melProfiler.mll",
        # "sceneAssembly.mll",  # cause crash in batch
        "rtgExport.mll",
        "atomImportExport.mll",
        "tiffFloatReader.mll",
        "ge2Export.mll",
        "vrml2Export.mll",
        "openInventor.mll",
        "AutodeskPacketFile.mll",
        "cgfxShader.mll",
        "fltTranslator.mll",
        "stereoCamera.mll",
        "OneClick.mll",
        "studioImport.mll",
        "Fur.mll",
        "Unfold3D.mll",
        "VectorRender.mll",
        "dx11Shader.mll",
        "OpenEXRLoader.mll",
        "mayaHIK.mll",
        "MayaMuscle.mll",
        "modelingToolkit.mll",
        "shaderFXPlugin.mll",
        "bullet.mll",
        "AbcBullet.mll",
        "AbcImport.mll",
        "AbcExport.mll",
        "gpuCache.mll",
        "mayaCharacterization.mll",
        "Turtle.mll",
        "bifrostvisplugin.mll",
        "bifrostshellnode.mll",
        "BifrostMain.mll",
        "fbxmaya.mll",
        "Substance.mll",
        "xgenToolkit.mll"
    ]

    def _l(name):
        try:
            # print "load plugin load: ", name
            cmds.loadPlugin(name)
        except:
            pass
            # print "pass plugin load: ", name

    for n in default_plugins:
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


def dump_sigle_id(id):
    load_plugins()
    dump_node_by_id(id)


def dump_indice(indice):
    load_plugins()
    for id in indice:
        dump_node_by_id(id)


def dump_id_range_using_multiprocessing():

    import multiprocessing as mp
    import itertools  # python 2.x can not iterate over 'long int' cause overflow error
    range = lambda start, stop: iter(itertools.count(start).next, stop)

    process_count = 7  # mp.cpu_count()
    po = mp.Pool(process_count)
    po.map(initialize_process, xrange(process_count))

    start = 0x30000000
    steps = 0x00001000
    end = 0x90000001

    while start < end:
        # print('start processing...', start)
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
    dump_id_range_using_multiprocessing()
