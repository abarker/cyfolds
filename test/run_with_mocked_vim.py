#!/usr/bin/env python3
"""

Usage:
    python3 test_cyfolds <pythonfile.py>

This program tests the `cyfolds` program by running it on a `.py` file of
code and printing out the results.  The folds are all shown next to their
lines.  With no arguments it runs some simple builtin tests.

For even more info, turn on the DEBUG flag in `cyfolds.pyx`, recompile, and
then run this program.  More info will be printed as the program runs.

Note that since the Vim module is mocked via an ordinary class the hashing
method is used to test for dirty cache.  Only the Cython part of the code
is tested by this program.

"""
#==============================================================================
# This file is part of the Cyfolds package, Copyright (c) 2019 Allen Barker.
# License details (MIT) can be found in the file LICENSE.
#==============================================================================

import sys
sys.path.insert(1,"../python3")

import cyfolds
from cyfolds import get_foldlevels, setup_regex_pattern

setup_regex_pattern()

cyfolds.TESTING = True

test_string = r'''
def egg():
"""Docstring."""
    for i in range(len):
    i = "egg"
    j = 'egg'
    k = "'egg'"
hello = (a,
         b)

class e(
 object):
x = "xxx
     yy"
'''

# Note the get_foldlevels fun is passed to vim, which numbers lines from 1.
# BUT the vim/python buffer vim.current.buffer IS indexed from zero.
# For that reason the prints of lines below do not match the get_foldlevels calls.

def run_for_test_string():
    """Run on the test string above."""
    print()
    lines = test_string.splitlines()
    flevels = get_foldlevels(
                           shiftwidth=4,
                           lines_of_module_docstrings=-1,
                           lines_of_fun_and_class_docstrings=-1,
                           test_buffer=lines)
    for i in range(0,14):
        print(lines[i], end="")
        print("\t\t#", flevels[i])


def print_results_for_file(filename):
    """Run the get_foldlevels calculator on the file and print the results."""
    print()
    print("="*5, filename, "="*19)
    print()

    with open(filename, "r") as f:
        test_code = f.read()

    test_code = test_code.splitlines()
    flevels = get_foldlevels(
                           shiftwidth=4,
                           lines_of_module_docstrings=-1,
                           lines_of_fun_and_class_docstrings=-1,
                           test_buffer=test_code)

    for lnum in range(len(test_code)):
        print("{:4}{:3}:".format(lnum, flevels[lnum]), test_code[lnum])


def get_fold_list(filename, writefile=""):
    """Return the list of folds for the lines in the file `filename`."""
    # TODO: create a params named tuple to pass in.
    with open(filename, "r") as f:
        test_code = f.read()

    test_code = test_code.splitlines()
    flevels = get_foldlevels(
                           shiftwidth=4,
                           lines_of_module_docstrings=-1,
                           lines_of_fun_and_class_docstrings=-1,
                           test_buffer=test_code)

    if writefile:
        with open(writefile, "w") as f:
            f.writelines(str(fold) + "\n" for fold in flevels)
    return flevels


if __name__ == "__main__":

    if len(sys.argv) > 1:
        filename = sys.argv[1]
        print_results_for_file(filename)
    else:
        run_for_test_string()
        print_results_for_file("example_foldlevels.py")

