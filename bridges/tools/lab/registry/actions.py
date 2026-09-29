"""Action registry helpers for compat diagnostic action bridges."""


class ActionRegistry:
    """Owns one diagnostic action registry for a single bridge entrypoint.

    ``platform`` is the app the registry's actions drive (``instagram``, ``tiktok``): a detection
    checks that the screen it answered on is that app's.
    """

    def __init__(self, platform: str | None = None):
        self.platform = platform
        self.actions: dict = {}
        #: The ids registered by `detection`: the yes/no questions of the screen.
        self.detections: set = set()

    def action(self, action_id: str):
        """Decorator to register a diagnostic action."""

        def decorator(fn):
            self.actions[action_id] = fn
            return fn

        return decorator

    def detection(self, action_id: str):
        """Decorator to register a yes/no question of the screen.

        The decorated function calls the production detection and returns its answer (True, False,
        or None when it could not tell); the Lab reports it through `detection_answer`: success
        with the answer, or a failure when the screen could not be read.
        """
        from bridges.tools.lab.action_test.detection_answer import detection_answer

        platform = self.platform
        if not platform:
            raise ValueError(f"{action_id}: a detection needs the registry's platform, to check the screen is its app's")

        def decorator(fn):
            def answered(a, p):
                return detection_answer(action_id, fn(a, p), device=a.device, platform=platform)

            answered.__name__ = fn.__name__
            answered.__doc__ = fn.__doc__
            self.actions[action_id] = answered
            self.detections.add(action_id)
            return fn

        return decorator


__all__ = ["ActionRegistry"]
