"""Action registry helpers for compat diagnostic action bridges."""


class ActionRegistry:
    """Owns one diagnostic action registry for a single bridge entrypoint."""

    def __init__(self):
        self.actions: dict = {}

    def action(self, action_id: str):
        """Decorator to register a diagnostic action."""

        def decorator(fn):
            self.actions[action_id] = fn
            return fn

        return decorator


__all__ = ["ActionRegistry"]

