"""Test suite for the operations module."""

TEST_MODULES = [
    "test_commands",
    "test_workflows",
    "test_policies",
    "test_validators",
    "test_results",
    "test_integration",
]

TEST_CATEGORIES = {
    "unit": [
        "test_commands",
        "test_policies",
        "test_validators",
        "test_results",
    ],
    "integration": [
        "test_workflows",
        "test_integration",
    ],
    "performance": [
        "test_integration::TestPerformanceIntegration",
    ],
}

MARKERS = {
    "slow": "marks tests as slow running",
    "integration": "marks tests that require full system setup",
    "unit": "marks unit tests that test components in isolation",
}
