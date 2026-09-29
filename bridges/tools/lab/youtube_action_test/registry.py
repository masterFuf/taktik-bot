"""Action registry for YouTube diagnostic actions."""

ACTION_REGISTRY: dict = {}


def action(action_id: str):
    """Decorator to register a diagnostic action."""

    def decorator(fn):
        ACTION_REGISTRY[action_id] = fn
        return fn

    return decorator


__all__ = ["ACTION_REGISTRY", "action"]
