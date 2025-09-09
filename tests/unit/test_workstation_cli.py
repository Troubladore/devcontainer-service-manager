"""Tests for workstation CLI commands and debug functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner
import logging
from io import StringIO

from devcontainer_services.workstation.cli import setup
from devcontainer_services.workstation.setup import WorkstationOptimizer


class TestWorkstationCLI:
    """Test workstation CLI commands."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer')
    def test_validate_command_basic(self, mock_optimizer_class):
        """Test basic validate command execution."""
        mock_optimizer = Mock()
        mock_optimizer.system_info = {
            'platform': 'Linux',
            'is_wsl': False,
            'docker_available': True
        }
        mock_optimizer.validate_performance_setup.return_value = {}
        mock_optimizer_class.return_value = mock_optimizer
        
        with patch('devcontainer_services.workstation.cli.validate_workstation_setup') as mock_validate:
            mock_validate.return_value = {
                'system_info': mock_optimizer.system_info,
                'validation': {},
                'optimizer': mock_optimizer
            }
            
            result = self.runner.invoke(setup, ['validate'])
            
            assert result.exit_code == 0
            assert "Validating workstation setup" in result.output
            mock_validate.assert_called_once_with(debug_mode=False)
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer')
    def test_validate_command_with_debug_flag(self, mock_optimizer_class):
        """Test validate command with --debug flag."""
        mock_optimizer = Mock()
        mock_optimizer.system_info = {
            'platform': 'Linux',
            'is_wsl': False,
            'docker_available': True
        }
        mock_optimizer.validate_performance_setup.return_value = {}
        mock_optimizer_class.return_value = mock_optimizer
        
        with patch('devcontainer_services.workstation.cli.validate_workstation_setup') as mock_validate:
            mock_validate.return_value = {
                'system_info': mock_optimizer.system_info,
                'validation': {},
                'optimizer': mock_optimizer
            }
            
            result = self.runner.invoke(setup, ['validate', '--debug'])
            
            assert result.exit_code == 0
            assert "Debug mode enabled - showing detailed detection methods" in result.output
            mock_validate.assert_called_once_with(debug_mode=True)
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer')
    def test_validate_command_with_verbose_flag(self, mock_optimizer_class):
        """Test validate command with --verbose flag."""
        mock_optimizer = Mock()
        mock_optimizer.system_info = {
            'platform': 'Linux',
            'is_wsl': False,
            'docker_available': True
        }
        mock_optimizer.validate_performance_setup.return_value = {}
        mock_optimizer_class.return_value = mock_optimizer
        
        with patch('devcontainer_services.workstation.cli.validate_workstation_setup') as mock_validate:
            mock_validate.return_value = {
                'system_info': mock_optimizer.system_info,
                'validation': {},
                'optimizer': mock_optimizer
            }
            
            result = self.runner.invoke(setup, ['validate', '--verbose'])
            
            assert result.exit_code == 0
            assert "Verbose mode enabled - showing detailed information" in result.output
            mock_validate.assert_called_once_with(debug_mode=False)
    
    @patch('devcontainer_services.workstation.cli.WorkstationOptimizer')
    def test_wsl2_optimize_command_basic(self, mock_optimizer_class):
        """Test basic wsl2-optimize command."""
        mock_optimizer = Mock()
        mock_optimizer.system_info = {'is_wsl': True, 'wsl_version': '2'}
        mock_optimizer.optimize_wsl2_performance.return_value = True
        mock_optimizer_class.return_value = mock_optimizer
        
        result = self.runner.invoke(setup, ['wsl2-optimize'])
        
        assert result.exit_code == 0
        assert "Applying WSL2 performance optimizations" in result.output
        mock_optimizer_class.assert_called_once_with(debug_mode=False)
    
    @patch('devcontainer_services.workstation.cli.WorkstationOptimizer')
    def test_wsl2_optimize_command_with_debug(self, mock_optimizer_class):
        """Test wsl2-optimize command with --debug flag."""
        mock_optimizer = Mock()
        mock_optimizer.system_info = {'is_wsl': True, 'wsl_version': '2'}
        mock_optimizer.optimize_wsl2_performance.return_value = True
        mock_optimizer_class.return_value = mock_optimizer
        
        result = self.runner.invoke(setup, ['wsl2-optimize', '--debug'])
        
        assert result.exit_code == 0
        assert "Debug mode enabled - showing detailed WSL2 detection and optimization steps" in result.output
        mock_optimizer_class.assert_called_once_with(debug_mode=True)
    
    @patch('devcontainer_services.workstation.cli.WorkstationOptimizer')  
    def test_wsl2_optimize_non_wsl_environment(self, mock_optimizer_class):
        """Test wsl2-optimize command fails gracefully on non-WSL."""
        mock_optimizer = Mock()
        mock_optimizer.system_info = {'is_wsl': False}
        mock_optimizer_class.return_value = mock_optimizer
        
        result = self.runner.invoke(setup, ['wsl2-optimize'])
        
        assert result.exit_code == 0
        assert "This command only works in WSL environments" in result.output
        # Should not call optimize_wsl2_performance
        mock_optimizer.optimize_wsl2_performance.assert_not_called()


class TestWorkstationOptimizerDebugMode:
    """Test WorkstationOptimizer debug functionality."""
    
    def test_optimizer_debug_mode_enabled(self):
        """Test WorkstationOptimizer with debug mode enabled."""
        with patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info') as mock_detect:
            mock_detect.return_value = {'platform': 'Linux', 'is_wsl': False}
            
            optimizer = WorkstationOptimizer(debug_mode=True)
            
            assert optimizer.debug_mode is True
            assert hasattr(optimizer, '_debug_print')
    
    def test_optimizer_debug_mode_disabled(self):
        """Test WorkstationOptimizer with debug mode disabled."""
        with patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info') as mock_detect:
            mock_detect.return_value = {'platform': 'Linux', 'is_wsl': False}
            
            optimizer = WorkstationOptimizer(debug_mode=False)
            
            assert optimizer.debug_mode is False
    
    def test_debug_print_with_debug_enabled(self):
        """Test _debug_print method when debug mode is enabled."""
        with patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info') as mock_detect:
            mock_detect.return_value = {'platform': 'Linux', 'is_wsl': False}
            
            optimizer = WorkstationOptimizer(debug_mode=True)
            
            with patch('builtins.print') as mock_print:
                optimizer._debug_print("Test message")
                # Should call print with instance ID format
                expected_call = f"DEBUG[#{optimizer.instance_id}]: Test message"
                mock_print.assert_called_with(expected_call)
    
    def test_debug_print_with_debug_disabled(self):
        """Test _debug_print method when debug mode is disabled."""
        with patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info') as mock_detect:
            mock_detect.return_value = {'platform': 'Linux', 'is_wsl': False}
            
            optimizer = WorkstationOptimizer(debug_mode=False)
            
            with patch('builtins.print') as mock_print:
                optimizer._debug_print("Test message")
                mock_print.assert_not_called()


class TestWSL2DebugDetection:
    """Test WSL2 detection with debug output."""
    
    @patch('builtins.open', side_effect=FileNotFoundError)
    @patch('os.environ', {})
    @patch('subprocess.run')
    @patch('pathlib.Path.exists', return_value=False)
    def test_wsl2_detection_all_methods_fail_with_debug(self, mock_path_exists, mock_subprocess, mock_environ):
        """Test WSL2 detection failure with debug output."""
        mock_subprocess.return_value = Mock(returncode=1, stdout='', stderr='')
        
        with patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info'):
            optimizer = WorkstationOptimizer(debug_mode=True)
            
            with patch('builtins.print') as mock_print:
                result = optimizer._is_wsl()
                
                assert result is False
                # Should have printed debug messages for each method
                debug_calls = [call for call in mock_print.call_args_list if 'DEBUG[#' in str(call)]
                assert len(debug_calls) > 6  # Should be more than 6 debug calls (start + 6 methods + end)
                
                # Check for specific debug messages
                debug_messages = [str(call) for call in debug_calls]
                assert any("Starting WSL2 detection using 6 different methods" in msg for msg in debug_messages)
                assert any("WSL NOT DETECTED: All 6 detection methods failed" in msg for msg in debug_messages)


class TestValidateWorkstationSetupDebugMode:
    """Test validate_workstation_setup function with debug mode."""
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer')
    def test_validate_workstation_setup_debug_enabled(self, mock_optimizer_class):
        """Test validate_workstation_setup passes debug_mode correctly."""
        from devcontainer_services.workstation.setup import validate_workstation_setup
        
        mock_optimizer = Mock()
        mock_optimizer.system_info = {'platform': 'Linux', 'is_wsl': False, 'docker_available': True}
        mock_optimizer.validate_performance_setup.return_value = {}
        mock_optimizer_class.return_value = mock_optimizer
        
        result = validate_workstation_setup(debug_mode=True)
        
        mock_optimizer_class.assert_called_once_with(debug_mode=True)
        assert result['system_info'] == mock_optimizer.system_info
        assert result['validation'] == {}
        assert result['optimizer'] == mock_optimizer
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer')
    def test_validate_workstation_setup_debug_disabled(self, mock_optimizer_class):
        """Test validate_workstation_setup with debug disabled."""
        from devcontainer_services.workstation.setup import validate_workstation_setup
        
        mock_optimizer = Mock()
        mock_optimizer.system_info = {'platform': 'Linux', 'is_wsl': False, 'docker_available': True}
        mock_optimizer.validate_performance_setup.return_value = {}
        mock_optimizer_class.return_value = mock_optimizer
        
        result = validate_workstation_setup(debug_mode=False)
        
        mock_optimizer_class.assert_called_once_with(debug_mode=False)
        assert result['system_info'] == mock_optimizer.system_info


if __name__ == '__main__':
    pytest.main([__file__])