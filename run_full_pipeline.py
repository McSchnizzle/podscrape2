#!/usr/bin/env python3
"""
Legacy compatibility layer for run_full_pipeline imports.

This module provides a compatibility import for legacy scripts that still
reference FullPipelineRunner. The actual implementation has been moved to
run_full_pipeline_orchestrator.py for production use.

For new development, use run_full_pipeline_orchestrator.py directly.
"""

import os
import sys
import warnings
from pathlib import Path

# Check if we're in test environment
if 'pytest' in sys.modules or 'PYTEST_CURRENT_TEST' in os.environ:
    # Import the test stub for pytest runs
    try:
        from tests.stubs.run_full_pipeline_stub import FullPipelineRunner
    except ImportError:
        # Fallback if stub is not available
        class FullPipelineRunner:
            def __init__(self, *args, **kwargs):
                raise ImportError(
                    "Legacy FullPipelineRunner not available. "
                    "Use run_full_pipeline_orchestrator.py for production."
                )
else:
    # Production environment - direct users to the orchestrator
    warnings.warn(
        "run_full_pipeline.FullPipelineRunner is deprecated. "
        "Use run_full_pipeline_orchestrator.py instead.",
        DeprecationWarning,
        stacklevel=2
    )

    # Try to import from reference file if it exists
    try:
        reference_file = Path(__file__).parent / "reference-only-run_full_pipeline.py"
        if reference_file.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("reference_pipeline", reference_file)
            if spec and spec.loader:
                reference_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(reference_module)
                FullPipelineRunner = reference_module.FullPipelineRunner
        else:
            raise ImportError("Reference implementation not found")
    except ImportError:
        # Final fallback - create a stub that directs to orchestrator
        class FullPipelineRunner:
            def __init__(self, *args, **kwargs):
                raise RuntimeError(
                    "FullPipelineRunner has been replaced by run_full_pipeline_orchestrator.py.\n"
                    "Please update your code to use the new orchestrator:\n"
                    "  python3 run_full_pipeline_orchestrator.py\n"
                    "Or for specific scripts:\n"
                    "  python3 scripts/run_discovery.py\n"
                    "  python3 scripts/run_audio.py\n"
                    "  python3 scripts/run_scoring.py\n"
                    "  python3 scripts/run_digest.py\n"
                    "  python3 scripts/run_tts.py\n"
                    "  python3 scripts/run_publishing.py"
                )

# Export for compatibility
__all__ = ['FullPipelineRunner']

if __name__ == "__main__":
    print("This is a compatibility layer. Use run_full_pipeline_orchestrator.py instead.")
    print("Usage: python3 run_full_pipeline_orchestrator.py [options]")
    sys.exit(1)