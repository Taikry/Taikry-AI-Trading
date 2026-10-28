"""
Global Pytest Configuration and Fixtures
Ensures workspace root is in sys.path.
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Disable background monitoring during tests to prevent blocking threads
os.environ["AUTO_START_MONITORING"] = "false"
os.environ["ENVIRONMENT"] = "testing"
