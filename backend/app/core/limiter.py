"""Shared slowapi Limiter instance.

Lives in its own module (rather than app/main.py) so route modules can
import and decorate with it without a circular import back into main.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
