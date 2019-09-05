#!/usr/bin/env python3
"""

Usage:
    python3 test_cyfolds <pythonfile.py>

This program tests the `cyfolds` program by running it on a `.py` file of
code and printing out the results.  The folds are all shown next to their
lines.  With no arguments it runs some simple builtin tests.

For even more info, turn on the DEBUG flag in `cyfolds.pyx`, recompile, and
then run this program.  More info will be printed as the program runs.

"""

# TODO: You currently need to switch to hash-computed dirty bit for cache, since
# no changes object to pass in.

import cyfolds
from cyfolds import get_foldlevel, setup_regex_pattern
import sys

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

# Note the get_foldlevel fun is passed to vim, which numbers lines from 1.
# BUT the vim/python buffer vim.current.buffer IS indexed from zero.
# For that reason the prints of lines below do not match the get_foldlevel calls.

def run_for_test_string():
    print()
    lines = test_string.splitlines()

    for i in range(1,15):
        print(lines[i-1], end="")
        flevel = get_foldlevel(lnum, cur_buffer_num=1, cur_undo_sequence=-1,
                               foldnestmax=20, shiftwidth=4,
                               lines_of_module_docstrings=-1,
                               lines_of_fun_and_class_docstrings=-1,
                               test_buffer=lines)
        print("\t\t#", flevel)

def print_results_for_file(filename):
    """Run the get_foldlevel calculator on the file and print the results."""
    print()
    print("="*5, filename, "="*19)
    print()

    with open(filename, "r") as f:
        test_code = f.read()

    test_code = test_code.splitlines()

    for lnum in range(1,len(test_code)+1):
        flevel = get_foldlevel(lnum, cur_buffer_num=1, cur_undo_sequence=-1,
                               foldnestmax=20, shiftwidth=4,
                               lines_of_module_docstrings=-1,
                               lines_of_fun_and_class_docstrings=-1,
                               test_buffer=test_code)
        print("{:4}{:3}:".format(lnum-1, flevel), test_code[lnum-1])


def get_fold_list(filename, writefile=""):
    """Return the list of folds for the lines in the file `filename`."""
    # TODO: create a params named tuple to pass in.
    with open(filename, "r") as f:
        test_code = f.read()

    test_code = test_code.splitlines()

    fold_list = []
    for lnum in range(1,len(test_code)+1):
        flevel = get_foldlevel(lnum,
                               cur_buffer_num=1,
                               cur_undo_sequence=-1,
                               foldnestmax=20,
                               shiftwidth=4,
                               lines_of_module_docstrings=-1,
                               lines_of_fun_and_class_docstrings=-1,
                               test_buffer=test_code)
        fold_list.append(flevel)

    if writefile:
        with open(writefile, "w") as f:
            f.writelines(str(fold) + "\n" for fold in fold_list)
    return fold_list


if __name__ == "__main__":

    if len(sys.argv) > 1:
        filename = sys.argv[1]
        print_results_for_file(filename)
    else:
        run_for_test_string()
        print_results_for_file("example_foldlevels.py")

