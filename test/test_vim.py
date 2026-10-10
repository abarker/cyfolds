"""Pytest tests which run the plugin inside a real, headless Vim and compare the
foldlevels that Vim reports with those computed directly by `pyfolds`.

These catch problems that only show up inside Vim, such as Vim passing a
`vim.buffer` object instead of a list.  The tests are skipped if no Vim with
Python 3 support is found."""
#==============================================================================
# This file is part of the Cyfolds package, Copyright (c) 2019 Allen Barker.
# License details (MIT) can be found in the file LICENSE.
#==============================================================================

import os
import shutil
import subprocess
import sys

import pytest

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TEST_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "python3"))

import pyfolds

VIM = shutil.which("vim")

def vim_has_python3():
    """Return true if Vim is installed and has Python 3 support."""
    if not VIM:
        return False
    version = subprocess.run([VIM, "--version"], capture_output=True, text=True)
    return "+python3" in version.stdout

pytestmark = pytest.mark.skipif(not vim_has_python3(),
                                reason="No Vim with Python 3 support found.")

# Code using three-space indents, the cause of several folding bugs.
THREE_SPACE_CODE = '''\
def always_on_top(sleeptime, title=None):
   """Docstring."""
   time.sleep(sleeptime)

   if title:
      subprocess.Popen(["wmctrl", "-r", title])
   else:
      subprocess.Popen(["wmctrl", "-r", ":ACTIVE:"])

   def inner():
      return 1

x = 1
'''

VIM_SCRIPT = """\
set nocompatible
let &runtimepath = '{project_root},' . $VIMRUNTIME
{force_pure_python}
filetype plugin on
edit {code_file}
setlocal shiftwidth=4
{update_folds}
let s:out = [py3eval('cyfolds_module.__name__')]
for s:lnum in range(1, line('$'))
    call add(s:out, string(foldlevel(s:lnum)))
endfor
call writefile(s:out, '{out_file}')
qall!
"""

def run_vim(tmp_path, code_file, force_pure_python, manual_foldmethod):
    """Run the plugin in a headless Vim on `code_file`.  Return the name of the
    module used and the list of foldlevels reported by Vim."""
    out_file = tmp_path / "vim_output.txt"
    if manual_foldmethod: # The plugin default, which sets folds from `expr` folds.
        update_folds = "call CyfoldsForceFoldUpdate()"
    else:
        update_folds = "setlocal foldmethod=expr\nnormal! zx"
    script = VIM_SCRIPT.format(
            project_root=PROJECT_ROOT, code_file=code_file, out_file=out_file,
            update_folds=update_folds,
            # Setting a module to None in `sys.modules` makes importing it fail.
            force_pure_python=("py3 import sys; sys.modules['cyfolds'] = None"
                               if force_pure_python else ""))
    script_file = tmp_path / "script.vim"
    script_file.write_text(script)

    # A temporary HOME keeps the user's own Vim files from being used.
    env = dict(os.environ, HOME=str(tmp_path))
    subprocess.run([VIM, "-N", "-u", "NONE", "-i", "NONE", "-es", "-S", str(script_file)],
                   env=env, stdin=subprocess.DEVNULL, timeout=60)
    assert out_file.exists(), "Vim did not write its output; the plugin may have failed."
    module_name, *foldlevels = out_file.read_text().splitlines()
    return module_name, [int(f) for f in foldlevels]


@pytest.mark.parametrize("manual_foldmethod", [False, True], ids=["expr", "manual"])
@pytest.mark.parametrize("module_name", ["cyfolds", "pyfolds"])
@pytest.mark.parametrize("code_name", ["basic_test_case.py", "nested_classes.py",
                                       "three_space_code"])
def test_vim_foldlevels(tmp_path, module_name, manual_foldmethod, code_name):
    """The foldlevels in Vim match the directly-computed ones."""
    if code_name == "three_space_code":
        code_file = tmp_path / "three_space_code.py"
        code_file.write_text(THREE_SPACE_CODE)
    else:
        code_file = os.path.join(TEST_DIR, code_name)
    with open(code_file) as f:
        code_lines = f.read().splitlines()

    used_module, vim_foldlevels = run_vim(tmp_path, code_file,
                                          force_pure_python=(module_name == "pyfolds"),
                                          manual_foldmethod=manual_foldmethod)
    if used_module != module_name:
        pytest.skip("Module cyfolds is not compiled for Vim's Python version.")

    pyfolds.setup_regex_pattern("class,def,async def") # The plugin default.
    expected = pyfolds.get_foldlevels(4, -1, -1, False, code_lines)
    assert vim_foldlevels == expected
