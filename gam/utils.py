import datetime
from decimal import Decimal

_PROTECTED_TYPES = (
    type(None), int, float, Decimal, datetime.datetime, datetime.date, datetime.time,
)


def is_protected_type(obj):
    """Determine if the object instance is of a protected type.

    Objects of protected types are preserved as-is when passed to
    force_text(strings_only=True).
    """
    return isinstance(obj, _PROTECTED_TYPES)


def force_bytes(string_like, encoding='utf-8', strings_only=False, errors='strict'):
    """
    Similar to smart_bytes, except that lazy instances are resolved to
    strings, rather than kept as lazy objects.

    If strings_only is True, don't convert (some) non-string-like objects.
    """
    # Handle the common case first for performance reasons.
    if isinstance(string_like, bytes):
        if encoding == 'utf-8':
            return string_like
        return string_like.decode('utf-8', errors).encode(encoding, errors)
    if strings_only and is_protected_type(string_like):
        return string_like
    if isinstance(string_like, memoryview):
        return bytes(string_like)
    return string_like.encode(encoding, errors)


def smart_bytes(string_like, encoding='utf-8', strings_only=False, errors='strict'):
    """
    Return a bytestring version of 's', encoded as specified in 'encoding'.

    If strings_only is True, don't convert (some) non-string-like objects.
    """
    return force_bytes(string_like, encoding, strings_only, errors)
