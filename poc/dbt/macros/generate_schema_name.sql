{#- Use the layer name (staging, intermediate, marts) as the schema, without the target prefix. -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name else target.schema }}
{%- endmacro %}
