import re

_PATTERNS = [
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"), "Bearer [REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "[API_KEY_REDACTED]"),
    (
        re.compile(
            r"(?i)\b(api[_ -]?key|access[_ -]?token|token|secret|password|passwd)\b"
            r"(\s*[:=]\s*)([^\s,;]{6,})"
        ),
        r"\1\2[REDACTED]",
    ),
]

def sanitize_text(text: str) -> str:
    value = text or ""
    for pattern, replacement in _PATTERNS:
        value = pattern.sub(replacement, value)
    return value
