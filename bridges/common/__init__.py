"""Infrastructure shared by every bridge. Import each capability from its own module.

This file stays empty: the launcher reaches its crash hooks through this package, before the bridge
is imported, and anything loaded here would fail before the hooks could report it.
"""
