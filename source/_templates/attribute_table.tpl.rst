{% extends node.tpl.rst %}

{% block attribute %}
            <tr>
                <td><h5>{{ k }}</h5>({{ v.short_name }})</td>
                <td>{{ v.type }}</td>
                <td>{{ v.value }} ({{ v.default_value }})</td>
                <td>{{ v.min_value }}/{{ v.max_value }}</td>
                <td>{{ v.flags }}</td>
            </tr><tr><td class="bar" colspan="6"></td></tr>

{% endblock %}
