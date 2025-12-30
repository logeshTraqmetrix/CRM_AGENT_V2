import re
from typing import Dict, Any


def validate_and_format_coql(query: str) -> Dict[str, Any]:
    errors = []
    warnings = []
    formatted = query.strip()

    if re.search(r'\bSELECT\s+\*\s+FROM\b', formatted, re.IGNORECASE):
        errors.append("❌ SELECT * is forbidden. Please specify explicit field names.")
        return {
            "valid": False,
            "formatted_query": None,
            "errors": errors,
            "warnings": warnings
        }

    operators = ['AND', 'OR', 'IN', 'NOT', 'IS', 'NULL', 'LIKE', 'BETWEEN']
    for op in operators:
        formatted = re.sub(rf'\b{op}\b', op.lower(), formatted, flags=re.IGNORECASE)

    if not re.search(r'\bWHERE\b', formatted, re.IGNORECASE):
        from_match = re.search(r'\bFROM\s+\w+', formatted, re.IGNORECASE)
        if from_match:
            formatted = (
                formatted[:from_match.end()]
                + " WHERE id is not null"
                + formatted[from_match.end():]
            )
            warnings.append("⚠️ Added default WHERE clause: 'id is not null'")

    where_match = re.search(
        r'\bWHERE\s+(.+?)(?:\s+ORDER\s+BY|\s+LIMIT|\s*$)',
        formatted,
        re.IGNORECASE | re.DOTALL
    )

    if where_match:
        clause = where_match.group(1).strip()
        if sum(len(re.findall(rf'\b{k}\b', clause, re.IGNORECASE)) for k in ['and', 'or']) > 1:
            if not (clause.startswith('(') and clause.endswith(')')):
                formatted = formatted.replace(clause, f"({clause})")
                warnings.append("⚠️ Added parentheses for multiple conditions")

    select_match = re.search(r'\bSELECT\s+(.+?)\s+FROM\b', formatted, re.IGNORECASE)
    if select_match:
        fields = select_match.group(1)

        updated_fields = re.sub(r'\bId\b', 'id', fields, flags=re.IGNORECASE)
        if fields != updated_fields:
            formatted = formatted.replace(fields, updated_fields)
            warnings.append("⚠️ Replaced SELECT field 'Id' with lowercase 'id'")

        if re.search(r'\w+\s+\w+(?!\s*,)', updated_fields):
            warnings.append("⚠️ Possible invalid field name with space detected")

    for val in re.findall(r'"([^"]+)"', formatted):
        formatted = formatted.replace(f'"{val}"', f"'{val}'")
    if '"' in formatted:
        warnings.append("⚠️ Converted double-quoted strings to single quotes")

    formatted = re.sub(r'=\s*null\b', 'is null', formatted, flags=re.IGNORECASE)
    formatted = re.sub(r'!=\s*null\b|<>\s*null\b', 'is not null', formatted, flags=re.IGNORECASE)

    forbidden_date_functions = [
        'current_date',
        'today',
        'now',
        'current_timestamp',
        'sysdate'
    ]

    for func in forbidden_date_functions:
        if re.search(rf'\b{func}\s*\(', formatted, re.IGNORECASE):
            errors.append(
                f"❌ Date/time function '{func.upper()}()' is not allowed. "
                "Use explicit ISO-8601 datetime literals instead (YYYY-MM-DDTHH:MM:SSZ)."
            )

    datetime_pattern = re.compile(
        r"'(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}Z?)'"
    )

    invalid_datetimes = []
    for m in datetime_pattern.finditer(formatted):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', m.group(1)):
            invalid_datetimes.append(m.group(1))

    if invalid_datetimes:
        errors.append(
            "❌ Invalid datetime format. Zoho COQL requires ISO-8601 UTC format "
            "(YYYY-MM-DDTHH:MM:SSZ). "
            f"Invalid values: {invalid_datetimes}"
        )

    if not re.search(r'\bFROM\s+\w+', formatted, re.IGNORECASE):
        errors.append("❌ Invalid query: Missing or invalid FROM clause")

    if not re.match(r'^\s*SELECT\s+.+\s+FROM\s+\w+', formatted, re.IGNORECASE):
        errors.append("❌ Invalid query structure")

    return {
        "valid": len(errors) == 0,
        "formatted_query": formatted,
        "errors": errors,
        "warnings": warnings
    }
