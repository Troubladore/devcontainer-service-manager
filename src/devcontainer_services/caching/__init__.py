"""Docker build caching and optimization module.

This module provides fingerprint-based Docker build caching with cross-repository
cache sharing via local Docker registry.

Key Features:
- 149x faster builds via intelligent caching
- Cross-repo cache sharing
- Automatic cleanup and maintenance
- WSL2 performance optimization
"""

from .fingerprint import DockerFingerprinter, CrossRepoCacheManager
from .cleanup import TestCleanupManager

__all__ = [
    "DockerFingerprinter",
    "CrossRepoCacheManager", 
    "TestCleanupManager",
]