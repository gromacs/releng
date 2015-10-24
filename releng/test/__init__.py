def load_tests(loader, tests, pattern):
    import os.path
    root = os.path.dirname(__file__)
    tests.addTests(loader.discover(start_dir=root, pattern='test_*.py'))
    return tests
