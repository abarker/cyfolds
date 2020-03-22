#!/usr/bin/env python3
"""

Write out the fold data lists for all the Python code files passed in on the
command line.  Files are written to the same filename with the extra extension
".testdata" added.  These can then be automatically checked against the folds
produced by the current version of Cyfolds by running
`test_generated_python_folds` or by just running `pytest` in the directory
which will run the testing program with nice output.

"""

import glob, os, sys
from run_with_mocked_vim import get_fold_list

def write_data_files():
    code_file_names = sys.argv[1:]
    for code_file_name in code_file_names:
        data_file_name = code_file_name + ".testdata"
        get_fold_list(code_file_name, writefile=data_file_name)

if __name__ == "__main__":
    write_data_files()

