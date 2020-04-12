#!/usr/bin/env python3
"""

Run the command to compile cyfolds, optionally removing unneeded files.

Note this command also works (but doesn't set compiler options):
   cythonize -a -i cyfolds.pyx

"""
import sys, os

python_executable = sys.executable

compile_command = python_executable + " setup.py build_ext --inplace"

print("Running compile command:\n   {}\n".format(compile_command))
os.system(compile_command)

yesno = input("\nCleanup unneeded files 'cyfolds.html' and 'cyfolds.c'"
              " (default is 'y')? [yn] ")

if yesno not in ["N", "n", "no", "No", "NO"]:
    os.remove("cyfolds.html")
    os.remove("cyfolds.c")

