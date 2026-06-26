# conftest.py — makes the project root importable by pytest
import sys
from pathlib import Path

# Insert the kisanai/ directory (project root) at the front of sys.path
sys.path.insert(0, str(Path(__file__).parent))
