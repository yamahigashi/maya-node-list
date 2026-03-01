{%- set categories = node.classification.split(':') if node.classification else [] %}
.. index::
    single: {{ node.typeName }}
    single: {{ id }}
    {%- for cat in categories %}
    single: category; {{ cat|replace('/', '; ') }}
    {%- endfor %}

{{ plugin }} - {{ node.typeName }} ({{ id }})
=======================================================================================================================================

:classification:
    {% if categories %}
    {% for cat in categories %}
    {{ cat }}
    {% endfor %}
    {% else %}
    (none)
    {% endif %}

:plugin:
    {{ node.pluginName or "(built-in)" }}

:id:
    {{ id }}

{% if not node.pluginName %}
:link:
    visit Autodesk Maya {{ maya_docs_year }} official reference `a link`_.

.. _a link: {{ maya_docs_base_url }}/{{ node.typeName }}.html
{% endif %}


Attributes ({{ node.attributeCount }})
--------------------------------------

{% macro attr(k, v, is_kid=False, last_elem=False, indent_lvl=0) -%}
{% if not is_kid %}
    {% if v.kids %}
            <tr class="parent indent{{ indent_lvl }} dotted" data-attr-name="{{ k|e }}">
    {% else %}
            <tr class="indent{{ indent_lvl }}" data-attr-name="{{ k|e }}">
    {% endif %}
{% else %}
    {% if last_elem and not v.kids %}
            <tr class="child indent{{ indent_lvl }} last" data-attr-name="{{ k|e }}">
    {% else %}
            <tr class="child indent{{ indent_lvl }} dotted" data-attr-name="{{ k|e }}">
    {% endif %}
{% endif %}
                <td class="attr_name" style="text-indent: {{ indent_lvl * 4 }}ex;"><span class="attr_label">{{ k }} ({{ v.short_name }})</span></td>
                <td class="attr_type">{{ v.display_type }}</td>
                <td class="attr_value">
                    <div class="attr_current">{{ v.display_value|replace(":", "<br>") }}</div>
                    {% if v.display_enum_items %}
                    <ul class="attr_enum_list">
                    {% for item in v.display_enum_items %}
                        <li class="attr_enum_item{% if item.is_default %} default{% endif %}">
                            {{ item.label }}
                            {% if item.is_default %}
                            <span class="enum_default">(default)</span>
                            {% endif %}
                        </li>
                    {% endfor %}
                    </ul>
                    {% endif %}
                    {% if v.display_default != "-" and v.display_default != v.display_value and not v.display_enum_items %}
                    <div class="attr_default">default: {{ v.display_default }}</div>
                    {% endif %}
                </td>
                <td class="attr_minmax">{{ v.display_minmax }}</td>
                <td class="attr_flags">{{ v.display_flags }}</td>
            </tr>

{% if v.kids %}
    {% for kid_k, kid_v in v.kids.items() %}
                {{ attr(kid_k, kid_v, True, loop.last, indent_lvl + 1) }}
    {% endfor %}
{% endif %}
{%- endmacro %}

.. raw:: html

    <table class="attribute">
        <tbody>
            <tr>
                <th class="attr_name">Long name (short name)</th>
                <th class="attr_type">Type</th>
                <th class="attr_default">Value</th>
                <th class="attr_minmax">Min/Max</th>
                <th class="attr_flags">Flags</th>
            </tr>
            {% if appear_in_cbox_attrs %}
            <tr>
                <th colspan="5">channel box</th>
            </tr>
            {% for k, v in appear_in_cbox_attrs.items() %}
                {{ attr(k, v) }}
            {% endfor %}
            {% endif %}
            {% if extern_attrs %}
            <tr>
                <th colspan="5">external visible attributes</th>
            </tr>
            {% for k, v in extern_attrs.items() %}
                {{ attr(k, v) }}
            {% endfor %}
            {% endif %}
            {% if extern_hidden %}
            <tr>
                <th colspan="5">external hidden attributes</th>
            </tr>
            {% for k, v in extern_hidden.items() %}
                {{ attr(k, v) }}
            {% endfor %}
            {% endif %}
            {% if internal_attrs %}
            <tr>
                <th colspan="5">internal attributes</th>
            </tr>
            {% for k, v in internal_attrs.items() %}
                {{ attr(k, v) }}
            {% endfor %}
            {% endif %}
        </tbody>
    </table>

{# vim: set ft=jinja: #}
