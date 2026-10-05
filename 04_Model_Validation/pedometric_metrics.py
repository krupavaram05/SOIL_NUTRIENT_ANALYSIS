#!/usr/bin/env python3
"""
================================================================================
DIGITAL SOIL NUTRIENT MAPPING (MBU FINAL YEAR PROJECT)
PEDOMETRIC METRICS CONVENIENCE PROXY
================================================================================
This script provides backward compatibility and convenient access to the
dedicated package located at:
  04_Model_Validation/pedometric_evaluation/

For the full module, documentation, and organized outputs, see:
  04_Model_Validation/pedometric_evaluation/pedometric_metrics.py
================================================================================
"""

import sys
from pathlib import Path

# Add pedometric_evaluation to Python path
suite_dir = Path(__file__).resolve().parent / "pedometric_evaluation"
if str(suite_dir) not in sys.path:
    sys.path.insert(0, str(suite_dir))

# Expose PedometricMetrics class and runner
from pedometric_metrics import PedometricMetrics, run_full_pedometric_evaluation

__all__ = ["PedometricMetrics", "run_full_pedometric_evaluation"]

if __name__ == "__main__":
    run_full_pedometric_evaluation()
