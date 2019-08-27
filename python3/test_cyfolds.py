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
import cyfolds
from cyfolds import foldlevel
import sys

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

# Note the foldlevel fun is passed to vim, which numbers lines from 1.
# BUT the vim/python buffer vim.current.buffer IS indexed from zero.
# For that reason the prints of lines below do not match the foldlevel calls.

def print_results_for_file(filename):
    """Run the foldlevel calculator on the file and print the results."""
    print()
    print("="*5, filename, "="*19)
    print()

    with open(filename, "r") as f:
        test_data = f.read()

    test_data = test_data.splitlines()

    for i in range(1,len(test_data)+1):
        flevel = foldlevel(i, 3, test_buffer=test_data)
        print("{:4}{:3}:".format(i-1, flevel), test_data[i-1])


def run_for_test_string():
    print()
    lines = test_string.splitlines()

    for i in range(1,15):
        print(lines[i-1], end="")
        print("\t\t#", foldlevel(i, 3, test_buffer=lines))


if __name__ == "__main__":

    if len(sys.argv) > 1:
        filename = sys.argv[1]
        print_results_for_file(filename)
    else:
        run_for_test_string()
        print_results_for_file("example_foldlevels.py")

