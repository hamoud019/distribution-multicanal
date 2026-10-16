{#- Matching keys for the golden customer (Part 6, section 2). Emails and phones are normalized, then
    hashed: staging and the later layers only hold the hash, never the email or phone itself. -#}

{#- The one place every key goes through: SHA-256 of a secret key followed by the value (Part 6, section 3),
    so a customer key cannot be recomputed from a guessable Shopify id or email without the key. The key
    comes from the environment (poc/keys.py); dbt stops if it is missing, rather than hash without it. -#}
{% macro pseudonymize(value) -%}
    sha256('{{ env_var("LSF_POC_PSEUDONYMIZATION_KEY") }}' || {{ value }})
{%- endmacro %}

{#- Lower-case and without spaces (rule 1). Empty when there is no email. -#}
{% macro email_key(email) -%}
    case when nullif(trim({{ email }}), '') is not null
        then {{ pseudonymize("lower(trim(" ~ email ~ "))") }} end
{%- endmacro %}

{#- International format, +33... (rule 2), together with the first name: a household sharing one phone has
    several first names, and it must not become one golden customer. Empty without a phone. -#}
{% macro phone_key(phone, first_name) -%}
    {%- set digits = "regexp_replace(" ~ phone ~ ", '[^0-9+]', '', 'g')" -%}
    {%- set international = "case when " ~ digits ~ " like '0%' then '+33' || substr(" ~ digits ~ ", 2)"
        ~ " when " ~ digits ~ " like '33%' then '+' || " ~ digits ~ " else " ~ digits ~ " end" -%}
    case when nullif(trim({{ phone }}), '') is not null and nullif(trim({{ first_name }}), '') is not null
        then {{ pseudonymize("(" ~ international ~ ") || '|' || lower(trim(" ~ first_name ~ "))") }} end
{%- endmacro %}

{#- True when the hashed value is on the erasure suppression list (Part 6, section 4, step 3). -#}
{% macro is_erased(hashed) -%}
    coalesce({{ hashed }} in (select key_hash from {{ source('meta', 'erasure_suppression') }}), false)
{%- endmacro %}
