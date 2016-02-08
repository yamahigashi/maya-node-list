.. index::
    single: {{ node.typeName }}
    single: {{ id }}
    {%- if node.classification %}
    {%- set categories = node.classification.split(':') %}
    {%- for cat in categories %}
    single: category; {{ cat|replace('/', '; ') }}
    {%- endfor %}
    {%- endif %}

{{ plugin }} - {{ node.typeName }} ({{ id }})
=======================================================================================================================================

:classification:
    {% for cat in categories %}
    {{ cat }}
    {% endfor %}

:plugin:
    {{ node.pluginName }}

:id:
    {{ id }}

{% if not node.pluginName %}
:link:
    visit Autodesk 2016 official reference `a link`_.

.. _a link: http://help.autodesk.com/cloudhelp/2016/ENU/Maya-Tech-Docs/Nodes/{{ node.typeName }}.html
{% endif %}


Attributes({{ node.attributeCount }})
--------------------------------------

{% macro attr(k, v, is_kid=False, last_elem=False, indent_lvl=0) -%}
{% if not is_kid %}
    {% if v.kids %}
            <tr class="parent indent{{ indent_lvl }} dotted">
    {% else %}
            <tr class="indent{{ indent_lvl }}">
    {% endif %}
{% else %}
    {% if last_elem and not v.kids %}
            <tr class="child indent{{ indent_lvl }} last">
    {% else %}
            <tr class="child indent{{ indent_lvl }} dotted">
    {% endif %}
{% endif %}
                <td class="attr_name" style="text-indent: {{ indent_lvl * 4 }}ex;"><h5>{{ k }} ({{ v.short_name }})</h5></td>
                <td class="attr_type">{{ v.type }}</td>
                <td class="attr_value">{{ v.value|replace(":", "</br>") }} ({{ v.default_value }})</td>
                <td class="attr_minmax">{{ v.min_value }}/{{ v.max_value }}</td>
                <td class="attr_flags">{{ v.flags }}</td>
            </tr>

{% if v.kids %}
    {% for kid_k, kid_v in v.kids.iteritems() %}
                {{ attr(kid_k, kid_v, True, loop.last, indent_lvl + 1) }}
    {% endfor %}
{% endif %}
{%- endmacro %}

{% macro escape_val(v) -%}
                {{ escape_val(v) }}
{%- endmacro %}

.. raw:: html

    <table class="attribute">
        <tbody>
            <tr>
                <th class="attr_name">Long name (short name)</th>
                <th class="attr_type">Type</th>
                <th class="attr_default">Value(Default)</th>
                <th class="attr_minmax">Min/Max</th>
                <th class="attr_flags">Flags</th>
            </tr>
            {% for k, v in apper_in_cbox_attrs.iteritems() %}
                {{ attr(k, v) }}
            {% endfor %}
            <tr>
                <th colspan="6">extern visible nodes</th>
            </tr>
            {% for k, v in extern_attrs.iteritems() %}
                {{ attr(k, v) }}
            {% endfor %}
            <tr>
                <th colspan="6">extern hidden nodes</th>
            </tr>
            {% for k, v in extern_hidden.iteritems() %}
                {{ attr(k, v) }}
            {% endfor %}
            <tr>
                <th colspan="6">internal nodes</th>
            </tr>
            {% for k, v in internal_attrs.iteritems() %}
                {{ attr(k, v) }}
            {% endfor %}
        </tbody>
    </table>
    
{# vim: set ft=jinja: #}
