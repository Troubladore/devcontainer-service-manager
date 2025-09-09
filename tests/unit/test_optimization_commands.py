"""Tests for optimization commands and rollback scenarios."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from click.testing import CliRunner

from devcontainer_services.workstation.cli import setup
from devcontainer_services.workstation.setup import WorkstationOptimizer


class TestOptimizeCommand:
    """Test the dcm-setup optimize command."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.mock_optimizer = Mock()
        self.mock_optimizer.system_info = {
            'platform': 'Linux',
            'is_wsl': True,
            'docker_available': True
        }
    
    def test_optimize_no_flags_shows_help(self):
        """Test optimize command without flags shows help."""
        with patch('devcontainer_services.workstation.cli.WorkstationOptimizer') as mock_cls:
            mock_cls.return_value = self.mock_optimizer
            
            result = self.runner.invoke(setup, ['optimize'])
            
            assert result.exit_code == 0
            assert "DCM Workstation Optimization" in result.output
            assert "Available optimizations:" in result.output
            assert "--docker-buildkit" in result.output
            assert "--wsl-config" in result.output
            assert "--filesystem" in result.output
            assert "--disk-cleanup" in result.output
            assert "--all" in result.output
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer')
    def test_optimize_all_flag(self, mock_optimizer_class):
        """Test optimize --all command."""
        mock_optimizer = Mock()
        mock_optimizer.apply_all_safe_optimizations.return_value = {
            'docker_buildkit': True,
            'filesystem_migration': True,
            'disk_cleanup': True
        }
        mock_optimizer_class.return_value = mock_optimizer
        
        result = self.runner.invoke(setup, ['optimize', '--all'])
        
        assert result.exit_code == 0
        assert "Applying all safe optimizations" in result.output
        assert "All 3 optimizations applied successfully" in result.output
        mock_optimizer.apply_all_safe_optimizations.assert_called_once_with(dry_run=False)
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer')
    def test_optimize_all_dry_run(self, mock_optimizer_class):
        """Test optimize --all --dry-run command."""
        mock_optimizer = Mock()
        mock_optimizer.apply_all_safe_optimizations.return_value = {
            'docker_buildkit': True,
            'filesystem_migration': True,
            'disk_cleanup': True
        }
        mock_optimizer_class.return_value = mock_optimizer
        
        result = self.runner.invoke(setup, ['optimize', '--all', '--dry-run'])
        
        assert result.exit_code == 0
        assert "Dry run mode - no changes will be made" in result.output
        assert "Applying all safe optimizations" in result.output
        mock_optimizer.apply_all_safe_optimizations.assert_called_once_with(dry_run=True)
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer')
    def test_optimize_individual_flags(self, mock_optimizer_class):
        """Test individual optimization flags."""
        mock_optimizer = Mock()
        mock_optimizer.apply_docker_buildkit_optimization.return_value = True
        mock_optimizer.apply_wsl_config_optimization.return_value = True
        mock_optimizer_class.return_value = mock_optimizer
        
        result = self.runner.invoke(setup, ['optimize', '--docker-buildkit', '--wsl-config'])
        
        assert result.exit_code == 0
        assert "Applying Docker BuildKit optimization" in result.output
        assert "Applying WSL2 configuration optimization" in result.output
        mock_optimizer.apply_docker_buildkit_optimization.assert_called_once_with(dry_run=False)
        mock_optimizer.apply_wsl_config_optimization.assert_called_once_with(dry_run=False)


class TestDockerBuildkitOptimization:
    """Test Docker BuildKit optimization with rollback scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.bashrc_path = Path(self.temp_dir) / '.bashrc'
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_apply_docker_buildkit_fresh_install(self):
        """Test applying Docker BuildKit on fresh system."""
        with patch('pathlib.Path.home', return_value=Path(self.temp_dir)):
            # Create empty .bashrc
            self.bashrc_path.write_text("")
            
            optimizer = WorkstationOptimizer(debug_mode=True)
            result = optimizer.apply_docker_buildkit_optimization(dry_run=False)
            
            assert result is True
            content = self.bashrc_path.read_text()
            assert "DOCKER_BUILDKIT=1" in content
            assert "COMPOSE_DOCKER_CLI_BUILD=1" in content
            assert "added by dcm-setup" in content
    
    def test_apply_docker_buildkit_already_configured(self):
        """Test applying Docker BuildKit when already configured."""
        with patch('pathlib.Path.home', return_value=Path(self.temp_dir)):
            # Create .bashrc with existing config
            self.bashrc_path.write_text("export DOCKER_BUILDKIT=1\n")
            
            optimizer = WorkstationOptimizer(debug_mode=True)
            result = optimizer.apply_docker_buildkit_optimization(dry_run=False)
            
            assert result is True
            content = self.bashrc_path.read_text()
            # Should not duplicate the config
            assert content.count("DOCKER_BUILDKIT=1") == 1
    
    def test_rollback_and_reapply_docker_buildkit(self):
        """Test removing Docker BuildKit config and reapplying."""
        with patch('pathlib.Path.home', return_value=Path(self.temp_dir)):
            # First apply the optimization
            self.bashrc_path.write_text("")
            optimizer = WorkstationOptimizer(debug_mode=True)
            
            # Apply
            result1 = optimizer.apply_docker_buildkit_optimization(dry_run=False)
            assert result1 is True
            assert "DOCKER_BUILDKIT=1" in self.bashrc_path.read_text()
            
            # Simulate rollback (remove the lines)
            content = self.bashrc_path.read_text()
            rollback_content = '\n'.join([
                line for line in content.split('\n') 
                if 'DOCKER_BUILDKIT' not in line and 'COMPOSE_DOCKER_CLI_BUILD' not in line and 'added by dcm-setup' not in line
            ])
            self.bashrc_path.write_text(rollback_content)
            
            # Verify removal
            assert "DOCKER_BUILDKIT=1" not in self.bashrc_path.read_text()
            
            # Reapply
            result2 = optimizer.apply_docker_buildkit_optimization(dry_run=False)
            assert result2 is True
            assert "DOCKER_BUILDKIT=1" in self.bashrc_path.read_text()
    
    def test_docker_buildkit_dry_run(self):
        """Test Docker BuildKit optimization in dry-run mode."""
        with patch('pathlib.Path.home', return_value=Path(self.temp_dir)):
            self.bashrc_path.write_text("")
            
            optimizer = WorkstationOptimizer(debug_mode=True)
            result = optimizer.apply_docker_buildkit_optimization(dry_run=True)
            
            assert result is True
            # Should not modify file in dry-run mode
            assert self.bashrc_path.read_text() == ""


class TestWSLConfigOptimization:
    """Test WSL2 .wslconfig optimization with rollback scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.windows_home = Path(self.temp_dir) / "mnt" / "c" / "Users"
        self.user_dir = self.windows_home / "testuser"
        self.wslconfig_path = self.user_dir / ".wslconfig"
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info')
    def test_apply_wsl_config_fresh_install(self, mock_detect):
        """Test applying WSL config on fresh system."""
        mock_detect.return_value = {'is_wsl': True, 'platform': 'Linux'}
        
        # Create directory structure
        self.user_dir.mkdir(parents=True)
        
        optimizer = WorkstationOptimizer()
        
        with patch('os.path.exists') as mock_exists, \
             patch('os.listdir') as mock_listdir, \
             patch('os.path.isdir') as mock_isdir, \
             patch('os.path.getsize') as mock_getsize, \
             patch('subprocess.run') as mock_subprocess, \
             patch('builtins.open', mock_open()) as mock_file:
            
            # Mock exists: Users directory exists, .wslconfig doesn't exist initially but appears after write
            mock_exists_calls = []
            def mock_exists_side_effect(path):
                mock_exists_calls.append(path)
                if path == '/mnt/c/Users':
                    return True
                elif path == '/mnt/c/Users/testuser/.wslconfig':
                    # Return True on second call (after file write) to simulate successful creation
                    return len([p for p in mock_exists_calls if p == path]) > 1
                return False
            
            mock_exists.side_effect = mock_exists_side_effect
            mock_listdir.return_value = ['testuser', 'Public']
            mock_isdir.return_value = True
            mock_getsize.return_value = 250  # Mock file size
            
            # Mock whoami subprocess call to return testuser
            mock_subprocess.return_value = Mock(returncode=0, stdout='testuser\n')
            
            result = optimizer.apply_wsl_config_optimization(dry_run=False)
            
            assert result is True
            # Verify file was opened for writing (no backup needed for fresh install)
            mock_file.assert_called_with('/mnt/c/Users/testuser/.wslconfig', 'w')
            # Verify the path exists check was called for verification
            assert any('/mnt/c/Users/testuser/.wslconfig' in str(call) for call in mock_exists.call_args_list)
            # Verify file size was checked for verification
            mock_getsize.assert_called_with('/mnt/c/Users/testuser/.wslconfig')
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info')
    def test_wsl_config_non_wsl_environment(self, mock_detect):
        """Test WSL config optimization on non-WSL system."""
        mock_detect.return_value = {'is_wsl': False, 'platform': 'Linux'}
        
        optimizer = WorkstationOptimizer()
        result = optimizer.apply_wsl_config_optimization(dry_run=False)
        
        assert result is True  # Should succeed but skip
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info')
    def test_wsl_config_dry_run(self, mock_detect):
        """Test WSL config optimization in dry-run mode."""
        mock_detect.return_value = {'is_wsl': True, 'platform': 'Linux'}
        
        optimizer = WorkstationOptimizer()
        result = optimizer.apply_wsl_config_optimization(dry_run=True)
        
        assert result is True
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info')
    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('os.path.isdir')
    @patch('subprocess.run')
    @patch('builtins.open', new_callable=mock_open)
    def test_wsl_config_multiple_users_debug(self, mock_file, mock_subprocess, mock_isdir, mock_listdir, mock_exists, mock_detect):
        """Test WSL config optimization with multiple users (provides manual instructions)."""
        mock_detect.return_value = {'is_wsl': True, 'wsl_version': '2', 'platform': 'Linux'}
        mock_exists.return_value = True
        mock_listdir.return_value = ['alice', 'bob', 'Public', 'Default']
        # Mock isdir to return True only for existing users
        mock_isdir.side_effect = lambda path: any(user in path for user in ['alice', 'bob', 'Public', 'Default'])
        
        # Mock whoami to return a user that doesn't exist in the directory (forcing fallback)
        mock_subprocess.return_value = Mock(returncode=0, stdout='nonexistentuser\n')
        
        optimizer = WorkstationOptimizer(debug_mode=True)  # Enable debug mode
        result = optimizer.apply_wsl_config_optimization(dry_run=False)
        
        assert result is True  # Should succeed but provide manual instructions
        # Verify listdir was called (may be called multiple times for main logic and fallback)
        assert mock_listdir.call_count >= 1
        assert any('/mnt/c/Users' in str(call) for call in mock_listdir.call_args_list)
        mock_file.assert_not_called()  # Should not write file when multiple users


class TestFilesystemMigrationOptimization:
    """Test filesystem migration helper with different scenarios."""
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info')
    @patch('os.getcwd')
    def test_filesystem_migration_windows_mount(self, mock_getcwd, mock_detect):
        """Test filesystem migration when in Windows mount."""
        mock_detect.return_value = {'is_wsl': True, 'platform': 'Linux'}
        mock_getcwd.return_value = '/mnt/c/Users/test/project'
        
        optimizer = WorkstationOptimizer()
        result = optimizer.apply_filesystem_migration_helper(dry_run=False)
        
        assert result is True
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info')
    @patch('os.getcwd')
    def test_filesystem_migration_wsl_native(self, mock_getcwd, mock_detect):
        """Test filesystem migration when already in WSL native filesystem."""
        mock_detect.return_value = {'is_wsl': True, 'platform': 'Linux'}
        mock_getcwd.return_value = '/home/user/project'
        
        optimizer = WorkstationOptimizer()
        result = optimizer.apply_filesystem_migration_helper(dry_run=False)
        
        assert result is True
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info')
    def test_filesystem_migration_non_wsl(self, mock_detect):
        """Test filesystem migration on non-WSL system."""
        mock_detect.return_value = {'is_wsl': False, 'platform': 'Linux'}
        
        optimizer = WorkstationOptimizer()
        result = optimizer.apply_filesystem_migration_helper(dry_run=False)
        
        assert result is True  # Should succeed but skip


class TestDiskCleanupOptimization:
    """Test disk cleanup optimization with different scenarios."""
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info')
    @patch('subprocess.run')
    def test_disk_cleanup_success(self, mock_run, mock_detect):
        """Test successful disk cleanup."""
        mock_detect.return_value = {'docker_available': True, 'platform': 'Linux'}
        mock_run.return_value = Mock(returncode=0, stdout='Total reclaimed space: 2.5GB')
        
        optimizer = WorkstationOptimizer()
        result = optimizer.apply_disk_cleanup_optimization(dry_run=False)
        
        assert result is True
        mock_run.assert_called_once_with(
            ['docker', 'system', 'prune', '-f'],
            capture_output=True,
            text=True,
            timeout=60
        )
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info')
    @patch('subprocess.run')
    def test_disk_cleanup_failure(self, mock_run, mock_detect):
        """Test disk cleanup failure."""
        mock_detect.return_value = {'docker_available': True, 'platform': 'Linux'}
        mock_run.return_value = Mock(returncode=1, stderr='Docker daemon not running')
        
        optimizer = WorkstationOptimizer()
        result = optimizer.apply_disk_cleanup_optimization(dry_run=False)
        
        assert result is False
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info')
    def test_disk_cleanup_no_docker(self, mock_detect):
        """Test disk cleanup when Docker unavailable."""
        mock_detect.return_value = {'docker_available': False, 'platform': 'Linux'}
        
        optimizer = WorkstationOptimizer()
        result = optimizer.apply_disk_cleanup_optimization(dry_run=False)
        
        assert result is True  # Should succeed but skip
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info')
    @patch('subprocess.run')
    def test_disk_cleanup_timeout(self, mock_run, mock_detect):
        """Test disk cleanup timeout."""
        import subprocess
        mock_detect.return_value = {'docker_available': True, 'platform': 'Linux'}
        mock_run.side_effect = subprocess.TimeoutExpired('docker', 60)
        
        optimizer = WorkstationOptimizer()
        result = optimizer.apply_disk_cleanup_optimization(dry_run=False)
        
        assert result is False
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info')
    def test_disk_cleanup_dry_run(self, mock_detect):
        """Test disk cleanup in dry-run mode."""
        mock_detect.return_value = {'docker_available': True, 'platform': 'Linux'}
        
        optimizer = WorkstationOptimizer()
        result = optimizer.apply_disk_cleanup_optimization(dry_run=True)
        
        assert result is True


class TestApplyAllSafeOptimizations:
    """Test the apply_all_safe_optimizations method."""
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info')
    def test_apply_all_safe_optimizations_success(self, mock_detect):
        """Test applying all safe optimizations successfully."""
        mock_detect.return_value = {'is_wsl': True, 'docker_available': True, 'platform': 'Linux'}
        
        optimizer = WorkstationOptimizer()
        
        with patch.object(optimizer, 'apply_docker_buildkit_optimization', return_value=True) as mock_docker, \
             patch.object(optimizer, 'apply_filesystem_migration_helper', return_value=True) as mock_fs, \
             patch.object(optimizer, 'apply_disk_cleanup_optimization', return_value=True) as mock_disk, \
             patch.object(optimizer, 'apply_wsl_config_optimization', return_value=True) as mock_wsl:
            
            result = optimizer.apply_all_safe_optimizations(dry_run=False)
            
            assert result == {
                'docker_buildkit': True,
                'filesystem_migration': True,
                'disk_cleanup': True,
                'wsl_config': True
            }
            
            mock_docker.assert_called_once_with(False)
            mock_fs.assert_called_once_with(False)
            mock_disk.assert_called_once_with(False)
            mock_wsl.assert_called_once_with(False)
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info')
    def test_apply_all_safe_optimizations_partial_failure(self, mock_detect):
        """Test applying all safe optimizations with partial failures."""
        mock_detect.return_value = {'is_wsl': True, 'docker_available': True, 'platform': 'Linux'}
        
        optimizer = WorkstationOptimizer()
        
        with patch.object(optimizer, 'apply_docker_buildkit_optimization', return_value=True), \
             patch.object(optimizer, 'apply_filesystem_migration_helper', return_value=False), \
             patch.object(optimizer, 'apply_disk_cleanup_optimization', return_value=True), \
             patch.object(optimizer, 'apply_wsl_config_optimization', return_value=True):
            
            result = optimizer.apply_all_safe_optimizations(dry_run=False)
            
            assert result == {
                'docker_buildkit': True,
                'filesystem_migration': False,
                'disk_cleanup': True,
                'wsl_config': True
            }
    
    @patch('devcontainer_services.workstation.setup.WorkstationOptimizer._detect_system_info')
    def test_apply_all_safe_optimizations_non_wsl(self, mock_detect):
        """Test applying all safe optimizations on non-WSL system."""
        mock_detect.return_value = {'is_wsl': False, 'docker_available': True, 'platform': 'Linux'}
        
        optimizer = WorkstationOptimizer()
        
        with patch.object(optimizer, 'apply_docker_buildkit_optimization', return_value=True) as mock_docker, \
             patch.object(optimizer, 'apply_filesystem_migration_helper', return_value=True) as mock_fs, \
             patch.object(optimizer, 'apply_disk_cleanup_optimization', return_value=True) as mock_disk:
            
            result = optimizer.apply_all_safe_optimizations(dry_run=False)
            
            # Should skip WSL config on non-WSL systems
            assert 'wsl_config' not in result
            assert result == {
                'docker_buildkit': True,
                'filesystem_migration': True,
                'disk_cleanup': True
            }


class TestOptimizationIdempotency:
    """Test that optimization commands are idempotent and handle re-application gracefully."""
    
    def test_multiple_docker_buildkit_applications(self):
        """Test applying Docker BuildKit optimization multiple times."""
        with tempfile.TemporaryDirectory() as temp_dir:
            bashrc_path = Path(temp_dir) / '.bashrc'
            bashrc_path.write_text("")
            
            with patch('pathlib.Path.home', return_value=Path(temp_dir)):
                optimizer = WorkstationOptimizer(debug_mode=True)
                
                # Apply first time
                result1 = optimizer.apply_docker_buildkit_optimization(dry_run=False)
                assert result1 is True
                content_after_first = bashrc_path.read_text()
                assert content_after_first.count("DOCKER_BUILDKIT=1") == 1
                
                # Apply second time (should be idempotent)
                result2 = optimizer.apply_docker_buildkit_optimization(dry_run=False)
                assert result2 is True
                content_after_second = bashrc_path.read_text()
                assert content_after_second.count("DOCKER_BUILDKIT=1") == 1
                assert content_after_first == content_after_second


if __name__ == '__main__':
    pytest.main([__file__, '-v'])