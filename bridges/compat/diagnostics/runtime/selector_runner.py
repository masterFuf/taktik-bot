"""Live selector execution helpers for compat selector diagnostics."""

from loguru import logger


def filter_selectors_by_domain(all_selectors: dict, domain_filter: list) -> dict:
    """Return selectors matching requested domains, or all selectors if no filter is set."""
    if not domain_filter:
        return all_selectors

    filtered = {}
    for action, entry in all_selectors.items():
        domain = action.split(".")[0]
        if domain in domain_filter:
            filtered[action] = entry
    return filtered


def run_selector_tests(device, all_selectors: dict, ipc) -> list[dict]:
    """Test every XPath from the selector registry against the live device."""
    results = []

    for action, entry in sorted(all_selectors.items()):
        domain = action.split(".")[0]
        field_name = action.split(".", 1)[1] if "." in action else action

        xpath_results = []
        action_has_match = False

        for xpath in entry.xpaths:
            found = False
            error_msg = None

            try:
                found = device.xpath(xpath).exists
            except Exception as exc:
                error_msg = str(exc)
                logger.warning(f"XPath error for {action}: {exc}")

            if found:
                action_has_match = True

            xpath_results.append(
                {
                    "xpath": xpath,
                    "found": found,
                    "error": error_msg,
                }
            )

        results.append(
            {
                "action": action,
                "domain": domain,
                "field": field_name,
                "source": entry.source,
                "has_match": action_has_match,
                "xpaths": xpath_results,
            }
        )

        if len(results) % 5 == 0:
            ipc.send("progress", current=len(results), total=len(all_selectors), action=action)

    return results


def summarize_selector_results(results: list[dict]) -> tuple[int, int, dict]:
    """Return passed/failed counts and per-domain summary."""
    passed = sum(1 for result in results if result["has_match"])
    failed = sum(1 for result in results if not result["has_match"])

    domain_summary = {}
    for result in results:
        domain = result["domain"]
        if domain not in domain_summary:
            domain_summary[domain] = {"total": 0, "passed": 0, "failed": 0}
        domain_summary[domain]["total"] += 1
        if result["has_match"]:
            domain_summary[domain]["passed"] += 1
        else:
            domain_summary[domain]["failed"] += 1

    return passed, failed, domain_summary


__all__ = ["filter_selectors_by_domain", "run_selector_tests", "summarize_selector_results"]

