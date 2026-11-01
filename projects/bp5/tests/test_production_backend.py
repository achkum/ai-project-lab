"""Run actual production acceptance suites in the delivery harness."""
import importlib.util
import sys
import unittest
from pathlib import Path

def load_tests(loader, tests, pattern):
    server = Path(__file__).resolve().parents[1] / 'server'
    sys.path.insert(0, str(server))
    suite = unittest.TestSuite()
    for filename in ('test_production.py', 'test_authored_library.py'):
        spec = importlib.util.spec_from_file_location('bp5_' + filename[:-3], server / filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        suite.addTests(loader.loadTestsFromModule(module))
    return suite
