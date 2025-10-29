"""Script to run all tests with coverage"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

if __name__ == '__main__':
    import pytest
    
    # Run tests with coverage
    args = [
        '--verbose',
        '--tb=short',
        '--color=yes',
        'tests/'
    ]
    
    sys.exit(pytest.main(args))