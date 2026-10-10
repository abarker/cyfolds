#!/usr/bin/env python3
"""

Run the command to compile cyfolds, optionally removing unneeded files.

The compiled module only works with the Python version used to compile it, so
that should be the same Python version that Vim uses.

Note this command also works (but doesn't set compiler options):
   cythonize -a -i cyfolds.pyx

"""
import sys, os, shutil, subprocess

# Run from this file's directory, so the script can be run from anywhere.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

compile_command = [sys.executable, "setup.py", "build_ext", "--inplace"]

print("Running compile command:\n   {}\n".format(" ".join(compile_command)))
if subprocess.call(compile_command) != 0:
    print("\nCompile failed.")
    sys.exit(1)

print("\nCompiled for Python {}.{}; Vim must use this Python version (check with"
      " ':py3 import sys; print(sys.version)' in Vim).".format(*sys.version_info[:2]))

yesno = input("\nCleanup unneeded files 'cyfolds.html', 'cyfolds.c', and the 'build'"
              " directory (default is 'y')? [yn] ")

if yesno not in ["N", "n", "no", "No", "NO"]:
    for filename in ["cyfolds.html", "cyfolds.c"]:
        if os.path.exists(filename):
            os.remove(filename)
    shutil.rmtree("build", ignore_errors=True)
