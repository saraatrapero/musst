"""Configuración común de pytest."""

from hypothesis import settings

settings.register_profile("default", max_examples=200, deadline=None)
settings.load_profile("default")
