#!/usr/bin/env python
"""
Wrapper script to run workflow tests from the project root
"""
import sys
import os

# Add team_04/PY to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'team_04', 'PY'))

# Change to the correct directory
os.chdir(os.path.join(os.path.dirname(__file__), 'team_04', 'PY'))

# Import and run the test
from design_main_test import main

if __name__ == "__main__":
    main()
