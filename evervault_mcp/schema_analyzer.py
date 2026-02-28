"""Schema analyzer -- detects PII/PCI fields and recommends encryption types.

This is a local tool (no API call). It pattern-matches field names against
known sensitive data patterns and recommends standard or deterministic
encryption. Recommendations are advisory only (see PRD deterministic
encryption note).
"""

from __future__ import annotations

import re
from typing import Any

# -- pattern definitions ------------------------------------------------------

# fields that indicate payment card data (PCI scope)
_PCI_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"card.?num",
        r"pan$",
        r"^pan[^a-z]",
        r"credit.?card",
        r"debit.?card",
        r"^cc.?num",
        r"^cvv",
        r"^cvc",
        r"^csv",
        r"card.?exp",
        r"expir",
        r"card.?holder",
    ]
]

# fields that indicate personally identifiable information
_PII_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"e.?mail",
        r"ssn",
        r"social.?sec",
        r"tax.?id",
        r"passport",
        r"driver.?lic",
        r"phone",
        r"mobile",
        r"^tel$",
        r"telephone",
        r"date.?of.?birth",
        r"^dob$",
        r"birth.?date",
        r"address",
        r"street",
        r"zip.?code",
        r"postal",
        r"first.?name",
        r"last.?name",
        r"full.?name",
        r"^name$",
        r"^ip$",
        r"ip.?addr",
        r"national.?id",
    ]
]

# fields where deterministic encryption is recommended (for indexing/lookup)
_DETERMINISTIC_FIELDS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"e.?mail",
        r"phone",
        r"mobile",
        r"^tel$",
        r"ssn",
        r"social.?sec",
        r"tax.?id",
        r"national.?id",
    ]
]


def analyze_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Analyze a JSON object/schema for sensitive fields.

    Args:
        schema: a JSON object whose keys represent field names.
            Values can be nested objects (analyzed recursively),
            type strings ("string", "number"), or sample values.

    Returns:
        dict with "fields" (list of field analyses) and "summary".
    """
    fields: list[dict[str, Any]] = []
    _walk(schema, [], fields)

    pci_count = sum(1 for f in fields if f["sensitivity"] == "pci")
    pii_count = sum(1 for f in fields if f["sensitivity"] == "pii")
    safe_count = sum(1 for f in fields if f["sensitivity"] == "safe")

    return {
        "fields": fields,
        "summary": {
            "total_fields": len(fields),
            "pci_fields": pci_count,
            "pii_fields": pii_count,
            "safe_fields": safe_count,
            "recommendation": _overall_recommendation(pci_count, pii_count),
        },
    }


def _walk(
    obj: Any,
    path: list[str],
    results: list[dict[str, Any]],
) -> None:
    """Recursively walk a JSON structure, analyzing each leaf field."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = path + [key]
            if isinstance(value, dict):
                # recurse into nested objects
                _walk(value, current_path, results)
            else:
                results.append(_analyze_field(current_path, key))
    # arrays and primitives at top level are treated as a single field
    elif path:
        results.append(_analyze_field(path, path[-1]))


def _analyze_field(path: list[str], field_name: str) -> dict[str, Any]:
    """Classify a single field by name."""
    field_path = ".".join(path)

    # check PCI first (higher severity)
    for pattern in _PCI_PATTERNS:
        if pattern.search(field_name):
            return {
                "field_path": field_path,
                "sensitivity": "pci",
                "suggested_encryption": _encryption_type(field_name),
                "reasoning": f"'{field_name}' matches PCI-scope pattern -- encrypt to keep cardholder data out of your infrastructure",
            }

    # then PII
    for pattern in _PII_PATTERNS:
        if pattern.search(field_name):
            enc_type = _encryption_type(field_name)
            reasoning = f"'{field_name}' matches PII pattern"
            if enc_type == "deterministic":
                reasoning += " -- deterministic recommended for lookup/indexing"
            return {
                "field_path": field_path,
                "sensitivity": "pii",
                "suggested_encryption": enc_type,
                "reasoning": reasoning,
            }

    # safe
    return {
        "field_path": field_path,
        "sensitivity": "safe",
        "suggested_encryption": "none",
        "reasoning": f"'{field_name}' does not match known sensitive data patterns",
    }


def _encryption_type(field_name: str) -> str:
    """Determine whether to recommend deterministic or standard encryption."""
    for pattern in _DETERMINISTIC_FIELDS:
        if pattern.search(field_name):
            return "deterministic"
    return "standard"


def _overall_recommendation(pci_count: int, pii_count: int) -> str:
    """Generate a one-line overall recommendation."""
    if pci_count > 0:
        return (
            f"Found {pci_count} PCI-scope field(s) -- "
            "encrypt immediately to reduce compliance scope"
        )
    if pii_count > 0:
        return (
            f"Found {pii_count} PII field(s) -- "
            "encrypt to protect personally identifiable information"
        )
    return "No sensitive fields detected -- schema looks clean"
