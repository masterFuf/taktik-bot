"""Instagram automation step tracing for compat workflow diagnostics.

The Lab no longer patches an engine it built itself: it hands this step hook to the production
launcher (`run_instagram_automation(step_hook=...)`), which wraps each workflow step with it.
"""


def trace_workflow_steps(tracer, ipc):
    """Step hook tracking each workflow step in the tracer and on the Lab's IPC."""

    def step_hook(action, run_step):
        action_type = action.get("type", "unknown")
        step_name = action.get("id", action_type)

        tracer.begin_step(step_name)
        ipc.send("workflow_step", step=step_name, status="running")

        try:
            result = run_step(action)
            tracer.end_step(success=result)
            ipc.send("workflow_step", step=step_name, status="done" if result else "failed")
            return result
        except Exception as exc:
            tracer.end_step(success=False, error=str(exc))
            ipc.send("workflow_step", step=step_name, status="error", error=str(exc))
            raise

    return step_hook


__all__ = ["trace_workflow_steps"]
