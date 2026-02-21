{% macro lbs_to_tonnes(column_name) %}
    ({{ column_name }} / 2204.62)
{% endmacro %}

{% macro lbs_to_short_tons(column_name) %}
    ({{ column_name }} / 2000.0)
{% endmacro %}

{% macro carbon_per_acre(carbon_col, tpa_col) %}
    ({{ carbon_col }} * {{ tpa_col }})
{% endmacro %}
