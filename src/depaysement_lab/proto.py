"""Compatibility shim.

The maintained implementation is `depaysement_lab.proto_v2`.
v0.5 keeps this module so older imports still work, but the defaults are now
English-first and instruction-tuned-first.
"""

from .proto_v2 import *  # noqa: F401,F403
