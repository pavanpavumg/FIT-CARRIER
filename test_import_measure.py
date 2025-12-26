import importlib.util
import sys
import os
import inspect

path = os.path.join(os.getcwd(), 'measure.py')
print('measure path:', path)

spec = importlib.util.spec_from_file_location('measure_test_mod', path)
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('mod.__file__ =', getattr(mod, '__file__', None))
print('public names =', sorted([n for n in dir(mod) if not n.startswith('__')]))
print('names containing "estimate":', [n for n in dir(mod) if 'estimate' in n.lower()])

print('\n--- measure.py source ---\n')
with open(path, 'r', encoding='utf-8') as f:
    print(f.read())
