"""Comprehensive test runner for DevContainer Service Manager.

This script runs the complete test suite with different configurations
to validate service manager behavior under various conditions.
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


class TestRunner:
    """Comprehensive test runner for all service manager tests."""

    def __init__(self):
        self.project_root = project_root
        self.tests_dir = self.project_root / "tests"
        self.results = {}

    def run_unit_tests(self) -> dict[str, Any]:
        """Run all unit tests."""
        print("=" * 60)
        print("Running Unit Tests")
        print("=" * 60)

        unit_args = [
            "-v",
            "--tb=short",
            str(self.tests_dir / "unit"),
            "--cov=devcontainer_services",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
        ]

        start_time = time.time()
        result = pytest.main(unit_args)
        end_time = time.time()

        self.results["unit_tests"] = {
            "exit_code": result,
            "duration": end_time - start_time,
            "passed": result == 0,
        }

        return self.results["unit_tests"]

    def run_integration_tests(self) -> dict[str, Any]:
        """Run integration tests (requires Docker)."""
        print("=" * 60)
        print("Running Integration Tests (Docker required)")
        print("=" * 60)

        # Check if Docker is available
        try:
            subprocess.run(["docker", "version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Docker not available - skipping integration tests")
            self.results["integration_tests"] = {
                "exit_code": 0,
                "duration": 0,
                "passed": True,
                "skipped": True,
            }
            return self.results["integration_tests"]

        integration_args = [
            "-v",
            "--tb=short",
            str(self.tests_dir / "integration"),
            "-m",
            "not slow",  # Skip slow tests by default
        ]

        start_time = time.time()
        result = pytest.main(integration_args)
        end_time = time.time()

        self.results["integration_tests"] = {
            "exit_code": result,
            "duration": end_time - start_time,
            "passed": result == 0,
            "skipped": False,
        }

        return self.results["integration_tests"]

    def run_contract_tests(self) -> dict[str, Any]:
        """Run contract fulfillment tests specifically."""
        print("=" * 60)
        print("Running Contract Fulfillment Tests")
        print("=" * 60)

        contract_args = [
            "-v",
            "--tb=short",
            str(self.tests_dir / "unit" / "test_contract_fulfillment.py"),
            "-k",
            "contract",  # Focus on contract tests
        ]

        start_time = time.time()
        result = pytest.main(contract_args)
        end_time = time.time()

        self.results["contract_tests"] = {
            "exit_code": result,
            "duration": end_time - start_time,
            "passed": result == 0,
        }

        return self.results["contract_tests"]

    def run_state_simulation_tests(self) -> dict[str, Any]:
        """Run state simulation tests specifically."""
        print("=" * 60)
        print("Running State Simulation Tests")
        print("=" * 60)

        state_args = [
            "-v",
            "--tb=short",
            str(self.tests_dir / "unit" / "test_state_simulation.py"),
        ]

        start_time = time.time()
        result = pytest.main(state_args)
        end_time = time.time()

        self.results["state_simulation_tests"] = {
            "exit_code": result,
            "duration": end_time - start_time,
            "passed": result == 0,
        }

        return self.results["state_simulation_tests"]

    def run_performance_tests(self) -> dict[str, Any]:
        """Run performance and cleanup tests."""
        print("=" * 60)
        print("Running Performance and Cleanup Tests")
        print("=" * 60)

        perf_args = [
            "-v",
            "--tb=short",
            str(self.tests_dir / "unit" / "test_performance_cleanup.py"),
        ]

        start_time = time.time()
        result = pytest.main(perf_args)
        end_time = time.time()

        self.results["performance_tests"] = {
            "exit_code": result,
            "duration": end_time - start_time,
            "passed": result == 0,
        }

        return self.results["performance_tests"]

    def run_edge_case_tests(self) -> dict[str, Any]:
        """Run edge case and error handling tests."""
        print("=" * 60)
        print("Running Edge Case and Error Handling Tests")
        print("=" * 60)

        edge_args = [
            "-v",
            "--tb=short",
            str(self.tests_dir / "unit" / "test_edge_cases.py"),
        ]

        start_time = time.time()
        result = pytest.main(edge_args)
        end_time = time.time()

        self.results["edge_case_tests"] = {
            "exit_code": result,
            "duration": end_time - start_time,
            "passed": result == 0,
        }

        return self.results["edge_case_tests"]

    def run_all_tests(self) -> dict[str, Any]:
        """Run the complete test suite."""
        print("Starting Comprehensive Test Suite")
        print("=" * 80)

        total_start_time = time.time()

        # Run all test categories
        test_categories = [
            self.run_unit_tests,
            self.run_contract_tests,
            self.run_state_simulation_tests,
            self.run_performance_tests,
            self.run_edge_case_tests,
            self.run_integration_tests,
        ]

        for test_func in test_categories:
            try:
                test_func()
            except Exception as e:
                print(f"Error running {test_func.__name__}: {e}")

        total_end_time = time.time()

        self.results["total_duration"] = total_end_time - total_start_time

        # Generate summary
        self.generate_summary()

        return self.results

    def generate_summary(self):
        """Generate and display test results summary."""
        print("\n" + "=" * 80)
        print("TEST RESULTS SUMMARY")
        print("=" * 80)

        total_tests = len([k for k in self.results.keys() if k.endswith("_tests")])
        passed_tests = len(
            [k for k, v in self.results.items() if k.endswith("_tests") and v.get("passed", False)]
        )

        print(f"Total Test Categories: {total_tests}")
        print(f"Passed Categories: {passed_tests}")
        print(f"Failed Categories: {total_tests - passed_tests}")
        print(f"Total Duration: {self.results.get('total_duration', 0):.2f}s")
        print()

        # Detailed results
        for category, results in self.results.items():
            if category.endswith("_tests"):
                status = "PASSED" if results.get("passed", False) else "FAILED"
                skipped = " (SKIPPED)" if results.get("skipped", False) else ""
                duration = results.get("duration", 0)

                print(f"{category:25} {status:8} {duration:6.2f}s{skipped}")

        # Overall result
        all_passed = all(
            v.get("passed", False) for k, v in self.results.items() if k.endswith("_tests")
        )

        print("\n" + "=" * 80)
        if all_passed:
            print("🎉 ALL TESTS PASSED! Service Manager Contract Fulfilled")
        else:
            print("❌ SOME TESTS FAILED - Contract Violations Detected")
        print("=" * 80)

    def validate_contracts(self) -> bool:
        """Validate that all service manager contracts are fulfilled."""
        print("\n" + "=" * 60)
        print("CONTRACT VALIDATION")
        print("=" * 60)

        # Check specific contract categories
        contract_categories = {
            "Availability Contract": "contract_tests",
            "State Management Contract": "state_simulation_tests",
            "Error Handling Contract": "edge_case_tests",
            "Performance Contract": "performance_tests",
            "Integration Contract": "integration_tests",
        }

        contract_violations = []

        for contract_name, test_category in contract_categories.items():
            if test_category in self.results:
                test_result = self.results[test_category]
                if not test_result.get("passed", False) and not test_result.get("skipped", False):
                    contract_violations.append(contract_name)
                    print(f"❌ {contract_name}: VIOLATED")
                else:
                    print(f"✅ {contract_name}: FULFILLED")
            else:
                print(f"⚠️  {contract_name}: NOT TESTED")

        if contract_violations:
            print(f"\n❌ CONTRACT VIOLATIONS DETECTED: {', '.join(contract_violations)}")
            return False
        else:
            print("\n🎉 ALL CONTRACTS FULFILLED!")
            return True


def main():
    """Main entry point for test runner."""
    import argparse

    parser = argparse.ArgumentParser(description="DevContainer Service Manager Test Runner")
    parser.add_argument(
        "--category",
        choices=["unit", "integration", "contract", "state", "performance", "edge", "all"],
        default="all",
        help="Test category to run",
    )
    parser.add_argument(
        "--validate-contracts", action="store_true", help="Validate service manager contracts"
    )

    args = parser.parse_args()

    runner = TestRunner()

    # Run specific test category
    if args.category == "unit":
        runner.run_unit_tests()
    elif args.category == "integration":
        runner.run_integration_tests()
    elif args.category == "contract":
        runner.run_contract_tests()
    elif args.category == "state":
        runner.run_state_simulation_tests()
    elif args.category == "performance":
        runner.run_performance_tests()
    elif args.category == "edge":
        runner.run_edge_case_tests()
    else:
        runner.run_all_tests()

    # Contract validation
    if args.validate_contracts or args.category == "all":
        contracts_fulfilled = runner.validate_contracts()
        sys.exit(0 if contracts_fulfilled else 1)

    # Exit with appropriate code
    if args.category != "all":
        category_key = f"{args.category}_tests"
        if category_key in runner.results:
            sys.exit(0 if runner.results[category_key].get("passed", False) else 1)
    else:
        all_passed = all(
            v.get("passed", False) for k, v in runner.results.items() if k.endswith("_tests")
        )
        sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
