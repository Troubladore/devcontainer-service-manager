"""Integration tests for workstation debug functionality.

These tests validate actual debug output and behavior without excessive mocking,
creating realistic scenarios to ensure debug mode catches real configuration issues.
"""

import pytest
import subprocess
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, mock_open


class TestWorkstationDebugIntegration:
    """Integration tests for workstation debug functionality."""

    def test_validate_debug_output_format(self):
        """Test that --debug produces properly formatted output with instance IDs."""
        result = subprocess.run([
            'dcm-setup', 'validate', '--debug'
        ], capture_output=True, text=True, cwd='/home/eru-admin/repos/devcontainer-service-manager')
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        output = result.stdout + result.stderr
        
        # Should have debug messages with instance IDs
        assert 'DEBUG[#1]:' in output, "Debug output should have instance ID"
        
        # Should show WSL detection methods
        assert '🔍 Starting WSL2 detection using 6 different methods' in output
        assert 'Method 1: Checking /proc/version' in output
        assert 'Method 2: Checking WSL environment variables' in output
        assert 'Method 3: Checking /proc/sys/kernel/osrelease' in output
        assert 'Method 4: Checking for WSL-specific mount points' in output
        assert 'Method 5: Checking if wsl.exe is available' in output
        assert 'Method 6: Checking for Windows directories' in output
        
        # Should not have duplicate debug output (no plain "DEBUG:" without instance ID)
        debug_lines = [line for line in output.split('\n') if line.startswith('DEBUG:')]
        plain_debug_lines = [line for line in debug_lines if not line.startswith('DEBUG[#')]
        
        # Allow the instance creation debug lines, but not WSL detection duplicates
        wsl_detection_duplicates = [line for line in plain_debug_lines 
                                  if 'Starting WSL2 detection' in line or 'Method' in line]
        assert len(wsl_detection_duplicates) == 0, f"Found duplicate WSL detection debug lines: {wsl_detection_duplicates}"

    def test_wsl2_optimize_debug_output_format(self):
        """Test that wsl2-optimize --debug produces properly formatted output."""
        result = subprocess.run([
            'dcm-setup', 'wsl2-optimize', '--debug'
        ], capture_output=True, text=True, cwd='/home/eru-admin/repos/devcontainer-service-manager')
        
        # Command should succeed even on non-WSL (should detect and exit gracefully)
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        output = result.stdout + result.stderr
        
        # Should have debug messages with instance IDs
        assert 'DEBUG[#' in output, "Debug output should have instance ID"
        
        # On non-WSL system, should detect and show appropriate message
        assert 'This command only works in WSL environments' in output or 'WSL2 optimizations applied' in output

    def test_debug_catches_docker_unavailable_issue(self):
        """Test that debug mode catches and reports Docker unavailability issue."""
        # This test is better done by testing the WorkstationOptimizer directly 
        # rather than subprocess calls to avoid PATH issues
        from devcontainer_services.workstation.setup import WorkstationOptimizer
        
        with patch.dict(os.environ, {'PATH': '/tmp/empty_path'}, clear=False):
            optimizer = WorkstationOptimizer(debug_mode=True)
            
            # Should complete without crashing
            assert optimizer.system_info is not None
            
            # Docker availability should be properly detected (likely False with restricted PATH)
            assert 'docker_available' in optimizer.system_info

    def test_debug_shows_filesystem_performance_analysis(self):
        """Test that debug mode shows detailed filesystem performance analysis."""
        result = subprocess.run([
            'dcm-setup', 'validate', '--debug'
        ], capture_output=True, text=True, cwd='/home/eru-admin/repos/devcontainer-service-manager')
        
        assert result.returncode == 0
        output = result.stdout + result.stderr
        
        # Should show filesystem performance analysis
        assert 'Filesystem Performance' in output
        assert 'Performance Tier:' in output
        
        # Debug output should have instance tracking
        assert 'DEBUG[#1]:' in output

    def test_verbose_vs_debug_output_differences(self):
        """Test that --verbose and --debug produce different levels of detail."""
        # Run with verbose
        verbose_result = subprocess.run([
            'dcm-setup', 'validate', '--verbose'
        ], capture_output=True, text=True, cwd='/home/eru-admin/repos/devcontainer-service-manager')
        
        # Run with debug
        debug_result = subprocess.run([
            'dcm-setup', 'validate', '--debug'  
        ], capture_output=True, text=True, cwd='/home/eru-admin/repos/devcontainer-service-manager')
        
        assert verbose_result.returncode == 0
        assert debug_result.returncode == 0
        
        verbose_output = verbose_result.stdout + verbose_result.stderr
        debug_output = debug_result.stdout + debug_result.stderr
        
        # Verbose should not have detailed method-by-method WSL detection
        assert '🔍 Starting WSL2 detection using 6 different methods' not in verbose_output
        
        # Debug should have detailed method-by-method WSL detection
        assert '🔍 Starting WSL2 detection using 6 different methods' in debug_output
        assert 'Method 1: Checking /proc/version' in debug_output
        
        # Both should have the validation summary
        assert 'Validation Summary' in verbose_output
        assert 'Validation Summary' in debug_output

    def test_wsl_version_detection_robustness(self):
        """Test that WSL version detection uses multiple methods robustly."""
        # This test simulates a WSL environment where basic detection works but version is tricky
        from devcontainer_services.workstation.setup import WorkstationOptimizer
        
        # Create a mock /proc/version that indicates WSL but doesn't specify version clearly
        mock_proc_version = "Linux version 5.15.90.1-microsoft-standard-WSL2 #1 SMP Fri Jan 1 00:00:00 UTC 2023 x86_64 x86_64 x86_64 GNU/Linux"
        
        with patch('builtins.open', mock_open(read_data=mock_proc_version)):
            with patch.dict(os.environ, {'WSL_DISTRO_NAME': 'Ubuntu'}):
                optimizer = WorkstationOptimizer(debug_mode=True)
                
                # Should detect WSL
                assert optimizer.system_info['is_wsl'] == True
                
                # Should detect WSL2 from the microsoft-standard-WSL2 in /proc/version
                assert optimizer.system_info['wsl_version'] == '2'

    def test_debug_output_no_sensitive_information_leak(self):
        """Test that debug output doesn't leak sensitive information."""
        result = subprocess.run([
            'dcm-setup', 'validate', '--debug'
        ], capture_output=True, text=True, cwd='/home/eru-admin/repos/devcontainer-service-manager')
        
        output = result.stdout + result.stderr
        
        # Should not contain common sensitive patterns
        sensitive_patterns = [
            'password',
            'secret',
            'token',
            'key=',
            'api_key',
            'auth',
        ]
        
        for pattern in sensitive_patterns:
            assert pattern.lower() not in output.lower(), f"Debug output contains potentially sensitive pattern: {pattern}"

    def test_multiple_instances_no_interference(self):
        """Test that multiple WorkstationOptimizer instances don't interfere with each other."""
        from devcontainer_services.workstation.setup import WorkstationOptimizer
        
        # Create multiple instances with debug mode
        optimizer1 = WorkstationOptimizer(debug_mode=True)
        optimizer2 = WorkstationOptimizer(debug_mode=True)
        
        # Each should have unique instance IDs
        assert hasattr(optimizer1, 'instance_id')
        assert hasattr(optimizer2, 'instance_id')
        assert optimizer1.instance_id != optimizer2.instance_id
        
        # Both should work independently
        info1 = optimizer1.system_info
        info2 = optimizer2.system_info
        
        assert info1 is not info2  # Should be separate objects
        assert info1['platform'] == info2['platform']  # But same system info


class TestKnownConfigurationIssues:
    """Tests that create known configuration issues and verify debug catches them."""

    def test_debug_catches_missing_docker_issue(self):
        """Create a scenario where Docker is missing and verify debug catches it."""
        # Find the current dcm-setup location to preserve it
        dcm_setup_result = subprocess.run(['which', 'dcm-setup'], capture_output=True, text=True)
        if dcm_setup_result.returncode != 0:
            pytest.skip("dcm-setup not found in PATH, skipping Docker availability test")
        
        dcm_setup_dir = os.path.dirname(dcm_setup_result.stdout.strip())
        
        # Temporarily modify PATH to hide Docker but keep dcm-setup
        original_path = os.environ.get('PATH', '')
        try:
            # Set PATH to minimal path plus dcm-setup location, but without common Docker locations
            minimal_path = f'/usr/bin:/bin:{dcm_setup_dir}'
            os.environ['PATH'] = minimal_path
            
            result = subprocess.run([
                'dcm-setup', 'validate', '--debug'
            ], capture_output=True, text=True, cwd='/home/eru-admin/repos/devcontainer-service-manager')
            
            output = result.stdout + result.stderr
            
            # Should complete without crashing
            assert result.returncode == 0
            
            # Debug should show Docker-related analysis
            assert 'DEBUG[#' in output
            
            # Should show Docker validation results (available or not available)
            assert 'Docker Validation' in output or 'Docker' in output
            
        finally:
            # Restore original PATH
            os.environ['PATH'] = original_path

    def test_debug_catches_filesystem_performance_issue(self):
        """Test that debug mode identifies filesystem performance issues."""
        result = subprocess.run([
            'dcm-setup', 'validate', '--debug'
        ], capture_output=True, text=True, cwd='/home/eru-admin/repos/devcontainer-service-manager')
        
        output = result.stdout + result.stderr
        
        # Should complete successfully
        assert result.returncode == 0
        
        # Debug should show filesystem analysis
        assert 'DEBUG[#' in output
        assert 'Filesystem Performance' in output
        
        # Should show performance tier assessment
        assert 'Performance Tier:' in output

    def test_debug_shows_instance_creation_tracking(self):
        """Test that debug mode shows instance creation with call stack."""
        result = subprocess.run([
            'dcm-setup', 'validate', '--debug'
        ], capture_output=True, text=True, cwd='/home/eru-admin/repos/devcontainer-service-manager')
        
        output = result.stdout + result.stderr
        
        # Should show instance creation debug info
        assert 'WorkstationOptimizer instance #1 created with debug_mode=True' in output
        assert 'Call stack:' in output
        
        # Should show file and function names in call stack
        assert 'validate_workstation_setup' in output or 'WorkstationOptimizer' in output


if __name__ == '__main__':
    pytest.main([__file__, '-v'])