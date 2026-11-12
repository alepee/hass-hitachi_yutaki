"""Register codecs: how a 16-bit register word maps to a value, both ways.

Every :class:`RegisterDefinition` declares one codec. ``decode`` turns the raw
word read from the gateway into the value the integration stores; ``encode``
turns a value back into the word to write. A raw word is never consumed or
written as is (#533).

Contract: for every value ``encode`` accepts, ``decode(encode(value)) ==
value``. ``encode`` raises ``ValueError`` (``TypeError`` for a non-number) for
a value the register cannot hold.
``decode`` returns ``None`` when the word carries no value (e.g. ``0xFFFF`` on
an unsigned register, or a code outside a closed domain).

The codec is picked from the register's documented type:

- a quantity (frequency, opening, setpoint in degrees): :data:`UNSIGNED`;
- a signed quantity, marked (*1) in the gateway documentation: :data:`SIGNED`;
- a quantity in tenths, marked (*3) where it applies: :data:`TENTHS`;
- a closed list of values (switch, mode, state, model): an :class:`EnumCodec`,
  so an undocumented word reads as unknown instead of as a value.

Codecs are generic types. The documented values of a register (states, modes,
models) belong to the gateway and are declared by its register map.
"""

from .enum_codec import EnumCodec, choice
from .prefixed import Prefixed
from .protocol import NOT_EXPOSED, RegisterCodec
from .scaled import TENTHS, Scaled
from .signed import SIGNED, Signed
from .unsigned import UNSIGNED, Unsigned

__all__ = [
    "EnumCodec",
    "NOT_EXPOSED",
    "Prefixed",
    "RegisterCodec",
    "SIGNED",
    "Scaled",
    "Signed",
    "TENTHS",
    "UNSIGNED",
    "Unsigned",
    "choice",
]
