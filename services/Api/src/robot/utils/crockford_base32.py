"""Utilidad para codificar UUIDs en Crockford Base32.

Usada para generar nombres de topics ROS: /robot/<base32>/command, etc.
"""

import uuid

_CROCKFORD_ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'


def uuid_to_crockford_base32(uuid_str: str | uuid.UUID) -> str:
    """Convierte un UUID (string o UUID) a Crockford Base32."""
    u = uuid.UUID(str(uuid_str))
    n = u.int
    if n == 0:
        return '0'
    chars = []
    while n > 0:
        chars.append(_CROCKFORD_ALPHABET[n & 0x1F])
        n >>= 5
    return ''.join(reversed(chars))
