
import re


def normalise_name(name: str) -> str:
    """Remove separators and convert an identifier to lowercase."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def match_tests(
    changed_functions: list[str],
    changed_classes: list[str],
    discovered_tests: list[dict]
) -> list[dict]:
    """
    Match discovered pytest tests against changed functions and classes.
    Returns recommended tests ranked by confidence.
    """

    recommendations = []

    for test in discovered_tests:
        test_name = normalise_name(test["test_name"])
        test_class = normalise_name(test.get("test_class") or "")

        reasons = []
        confidence = 0.0

        # Match changed functions against test function names.
        for function in changed_functions:
            normalised_function = normalise_name(function)

            if normalised_function and normalised_function in test_name:
                confidence = max(confidence, 0.95)
                reasons.append(
                    f"Test name directly matches changed function '{function}'"
                )

        # Match changed classes against test class or function names.
        for class_name in changed_classes:
            normalised_class = normalise_name(class_name)

            if not normalised_class:
                continue

            if (
                normalised_class in test_class
                or normalised_class in test_name
            ):
                confidence = max(confidence, 0.90)
                reasons.append(
                    f"Test is associated with changed class '{class_name}'"
                )

        # Only recommend tests with a meaningful match.
        if confidence == 0:
            continue

        if confidence >= 0.90:
            priority = "high"
        elif confidence >= 0.70:
            priority = "medium"
        else:
            priority = "low"

        recommendations.append({
            "test_file": test["test_file"],
            "test_name": test["test_name"],
            "priority": priority,
            "confidence": confidence,
            "reasons": reasons
        })

    recommendations.sort(
        key=lambda test: test["confidence"],
        reverse=True
    )

    return recommendations
