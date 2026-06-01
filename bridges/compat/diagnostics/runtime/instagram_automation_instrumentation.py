"""Instagram automation runner instrumentation for compat workflow diagnostics."""


def instrument_workflow_runner(automation, tracer, ipc) -> None:
    """Monkey-patch WorkflowRunner.run_workflow_step to track steps in the tracer."""
    runner = automation.workflow_runner
    original_run_step = runner.run_workflow_step

    def instrumented_run_step(action):
        action_type = action.get("type", "unknown")
        step_name = action.get("id", action_type)

        tracer.begin_step(step_name)
        ipc.send("workflow_step", step=step_name, status="running")

        try:
            result = original_run_step(action)
            tracer.end_step(success=result)
            ipc.send("workflow_step", step=step_name, status="done" if result else "failed")
            return result
        except Exception as exc:
            tracer.end_step(success=False, error=str(exc))
            ipc.send("workflow_step", step=step_name, status="error", error=str(exc))
            raise

    runner.run_workflow_step = instrumented_run_step


__all__ = ["instrument_workflow_runner"]
