"""Run the shipped API/storage/security suite through the delivery harness."""
import importlib.util
import sys
from pathlib import Path

def load_tests(loader, tests, pattern):
    server=Path(__file__).resolve().parents[1]/'server'
    sys.path.insert(0,str(server))
    spec=importlib.util.spec_from_file_location('bp5_backend_tests',server/'test_api.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return loader.loadTestsFromModule(module)
