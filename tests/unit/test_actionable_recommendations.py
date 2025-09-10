"""Tests to enforce that all optimization recommendations include actionable instructions.

This test suite ensures that every recommendation produced by dcm-setup validate
comes with clear, step-by-step instructions that users can follow to implement
the optimization.
"""

import re
from unittest.mock import patch

import pytest
from devcontainer_services.workstation.setup import WorkstationOptimizer, validate_workstation_setup


class TestActionableRecommendations:
    """Test that all recommendations include clear implementation instructions."""

    def test_all_recommendations_have_instructions(self):
        """Test that every recommendation includes actionable implementation steps."""
        # Create optimizer and run full validation
        optimizer = WorkstationOptimizer(debug_mode=False)
        validation_results = optimizer.validate_performance_setup()

        # Collect all recommendations from all validation categories
        all_recommendations = []

        for category, checks in validation_results.items():
            if isinstance(checks, dict) and "recommendations" in checks:
                for rec in checks["recommendations"]:
                    all_recommendations.append(
                        {"category": category, "text": rec, "recommendation": rec}
                    )

        # Ensure we have some recommendations to test (fail if none found)
        assert (
            len(all_recommendations) > 0
        ), "No recommendations found - test cannot validate actionable instructions"

        # Check each recommendation for actionable instructions
        for rec_info in all_recommendations:
            self._assert_recommendation_is_actionable(rec_info)

    def _assert_recommendation_is_actionable(self, rec_info):
        """Assert that a recommendation includes actionable implementation steps."""
        category = rec_info["category"]
        text = rec_info["text"]

        # Requirements for actionable recommendations:
        # 1. Should include specific commands, file paths, or configuration changes
        # 2. Should not be vague (avoid words like "consider", "maybe", "might")
        # 3. Should include HOW to implement, not just WHAT to do

        # Check for actionable elements
        actionable_indicators = [
            # Commands to run
            r"\$\s+\w+",  # $ command
            r"`[^`]+`",  # `command` or `file.conf`
            r"export \w+",  # export VARIABLE
            r'echo ["\'].+["\']',  # echo "content"
            r"sudo \w+",  # sudo command
            r"docker \w+",  # docker command
            r"npm \w+",  # npm command
            r"pip \w+",  # pip command
            r"apt \w+",  # apt command
            r"brew \w+",  # brew command
            # File operations
            r"\.bashrc",  # .bashrc
            r"\.zshrc",  # .zshrc
            r"\.profile",  # .profile
            r"\.env",  # .env
            r"~/",  # ~/path
            r"/etc/",  # /etc/path
            r"/usr/",  # /usr/path
            # Configuration patterns
            r"DOCKER_BUILDKIT=1",  # Environment variable setting
            r"--\w+",  # Command flags
            r"[A-Z_]+=\w+",  # Environment variable patterns
            # Step indicators
            r"\d+\.",  # 1. Step one
            r"Step \d+",  # Step 1
            r"Run:",  # Run: command
            r"Add:",  # Add: content
            r"Set:",  # Set: variable
            r"Create:",  # Create: file
            r"Edit:",  # Edit: file
        ]

        # Check if recommendation includes actionable elements
        has_actionable_content = any(
            re.search(pattern, text, re.IGNORECASE) for pattern in actionable_indicators
        )

        # Check for vague language (should be avoided)
        vague_patterns = [
            r"\bconsider\b",
            r"\bmight\b",
            r"\bmaybe\b",
            r"\bshould probably\b",
            r"\btry to\b",
        ]

        has_vague_language = any(
            re.search(pattern, text, re.IGNORECASE) for pattern in vague_patterns
        )

        # Assert requirements
        assert has_actionable_content, (
            f"Recommendation in category '{category}' lacks actionable instructions:\n"
            f"'{text}'\n\n"
            f"Recommendations should include specific commands, file paths, or configuration changes. "
            f"Examples:\n"
            f"- Commands: `export DOCKER_BUILDKIT=1` or `$ sudo systemctl restart docker`\n"
            f"- Files: Add to ~/.bashrc or Edit /etc/docker/daemon.json\n"
            f"- Steps: 1. Run command 2. Restart service 3. Verify change\n"
        )

        assert not has_vague_language, (
            f"Recommendation in category '{category}' uses vague language:\n"
            f"'{text}'\n\n"
            f"Avoid words like 'consider', 'might', 'maybe'. "
            f"Use direct instructions instead."
        )

        # Length check - actionable instructions should be substantial
        assert len(text) > 30, (
            f"Recommendation in category '{category}' is too brief to be actionable:\n"
            f"'{text}'\n\n"
            f"Actionable recommendations should include sufficient detail for implementation."
        )

    def test_docker_buildkit_recommendation_is_actionable(self):
        """Test specific case: Docker BuildKit recommendation should include implementation steps."""
        # Create a scenario where Docker BuildKit recommendation would be generated
        optimizer = WorkstationOptimizer(debug_mode=False)

        # Mock docker info to simulate BuildKit not enabled (no buildx in BuilderVersion)
        mock_docker_info = {
            "BuilderVersion": "1.0.0",  # Not starting with "buildx"
            "MemTotal": 8000000000,  # 8GB
            "Driver": "overlay2",
        }

        with patch.object(optimizer, "get_docker_info", return_value=mock_docker_info):
            docker_validation = optimizer._validate_docker_setup()

        # Should have BuildKit recommendation
        recommendations = docker_validation.get("recommendations", [])
        buildkit_recs = [r for r in recommendations if "BuildKit" in r or "buildkit" in r.lower()]

        if buildkit_recs:
            # If BuildKit recommendation exists, it should be actionable
            for rec in buildkit_recs:
                # Should include specific environment variable
                assert (
                    "DOCKER_BUILDKIT=1" in rec
                ), f"BuildKit recommendation should include 'DOCKER_BUILDKIT=1': {rec}"

                # Should include implementation steps
                actionable_elements = [
                    "echo",  # Command to run
                    ".bashrc",  # Shell config file
                    "source",  # Reload command
                    "1.",  # Numbered step
                ]

                has_implementation = any(element in rec for element in actionable_elements)
                assert (
                    has_implementation
                ), f"BuildKit recommendation should include implementation steps: {rec}"

    def test_wsl_filesystem_performance_recommendation_is_actionable(self):
        """Test WSL filesystem performance recommendations are actionable."""
        optimizer = WorkstationOptimizer(debug_mode=False)

        # Mock WSL environment with cross-filesystem mount (slow performance)
        with patch.object(
            optimizer, "system_info", {"is_wsl": True, "platform": "Linux", "wsl_version": "2"}
        ):
            # Mock current working directory as Windows mount (slow)
            with patch("os.getcwd", return_value="/mnt/c/projects/myproject"):
                fs_validation = optimizer._validate_filesystem_performance()

        # Should have filesystem performance recommendations
        recommendations = fs_validation.get("recommendations", [])
        fs_recs = [r for r in recommendations if "filesystem" in r.lower() or "mount" in r.lower()]

        if fs_recs:
            for rec in fs_recs:
                # Should include specific paths or commands
                actionable_elements = [
                    "~/",  # Home directory path
                    "mkdir",  # Command to create directory
                    "cd",  # Command to change directory
                    "git clone",  # Command to clone repos
                    "cp ",  # Command to copy files
                    "mv ",  # Command to move files
                ]

                has_implementation = any(element in rec for element in actionable_elements)
                assert (
                    has_implementation
                ), f"Filesystem recommendation should include implementation steps: {rec}"

    def test_resource_recommendations_are_actionable(self):
        """Test that resource-related recommendations include actionable steps."""
        optimizer = WorkstationOptimizer(debug_mode=False)

        # Mock low disk space scenario by patching the disk usage check
        # We'll mock the df command output to simulate low disk space
        mock_df_output = "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1        50G   48G   1.5G  97% /\n"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_df_output
            resource_validation = optimizer._validate_resource_availability()

        recommendations = resource_validation.get("recommendations", [])

        if recommendations:
            for rec in recommendations:
                # Resource recommendations should include specific actions
                actionable_elements = [
                    "docker system prune",  # Docker cleanup command
                    "sudo apt autoremove",  # Package cleanup
                    "rm ",  # File deletion
                    "du -h",  # Disk usage analysis
                    "ncdu",  # Disk usage tool
                    "GB",  # Specific size references
                ]

                has_implementation = any(element in rec for element in actionable_elements)
                assert (
                    has_implementation
                ), f"Resource recommendation should include implementation steps: {rec}"

    def test_recommendation_format_consistency(self):
        """Test that all recommendations follow consistent formatting for actionability."""
        optimizer = WorkstationOptimizer(debug_mode=False)
        validation_results = optimizer.validate_performance_setup()

        all_recommendations = []
        for _category, checks in validation_results.items():
            if isinstance(checks, dict) and "recommendations" in checks:
                for rec in checks["recommendations"]:
                    all_recommendations.append(rec)

        if all_recommendations:
            for rec in all_recommendations:
                # Recommendations should be properly formatted
                # Should not end with generic phrases
                bad_endings = [
                    "for better performance",
                    "to improve speed",
                    "for optimization",
                    "is recommended",
                ]

                rec_lower = rec.lower()
                for bad_ending in bad_endings:
                    assert not rec_lower.endswith(bad_ending), (
                        f"Recommendation ends with generic phrase instead of actionable instructions:\n"
                        f"'{rec}'\n"
                        f"Should include specific implementation steps."
                    )

    def test_validate_workstation_setup_shows_actionable_recommendations(self):
        """Test that the main validate function surfaces actionable recommendations."""
        # Run full validation
        results = validate_workstation_setup(debug_mode=False)
        validation = results["validation"]

        # Count total recommendations
        total_recommendations = 0
        for _category, checks in validation.items():
            if isinstance(checks, dict) and "recommendations" in checks:
                total_recommendations += len(checks["recommendations"])

        # If there are recommendations, they should all be actionable
        if total_recommendations > 0:
            # Spot check some recommendations for actionable content
            docker_checks = validation.get("docker", {})
            docker_recs = docker_checks.get("recommendations", [])

            for rec in docker_recs:
                # Docker recommendations should include specific implementation
                assert len(rec) > 20, f"Docker recommendation too brief: {rec}"

                # Should avoid vague language
                vague_words = ["consider", "might", "maybe", "should probably"]
                for vague in vague_words:
                    assert (
                        vague not in rec.lower()
                    ), f"Docker recommendation uses vague language '{vague}': {rec}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
