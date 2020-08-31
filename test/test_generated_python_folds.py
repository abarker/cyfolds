#!/usr/bin/env python3
"""

Can be run directly or with pytest.

Usage::
    pytest -v
    python3 test_generated_python_folds.py

Code to test the folds generated by cyfolds.pyx against the saved results.

Test data must be in files named with the name of the code file with the
`.testdata` extension added.   Cyfolds is run on the corresponding `.py`
file and the computed folds are compared.  This is done for all `.testfile`
files in the directory.

"""
#==============================================================================
# This file is part of the Cyfolds package, Copyright (c) 2019 Allen Barker.
# License details (MIT) can be found in the file LICENSE.
#==============================================================================

import glob, os, sys
from run_with_mocked_vim import get_fold_list

def test_on_files(verbose=False):
    if verbose:
        print("\nComparing generated folds with saved data...")

    data_file_names = glob.glob("*.testdata")
    error_found = False
    for data_file_name in data_file_names:
        if verbose:
            print("   ", data_file_name)
        with open(data_file_name, "r") as f:
            data_fold_list = f.readlines()
        data_fold_list = [d.strip() for d in data_fold_list]

        code_file_name = os.path.splitext(data_file_name)[0]
        computed_fold_list = get_fold_list(code_file_name)
        computed_fold_list = [str(c) for c in computed_fold_list]

        if len(computed_fold_list) != len(data_fold_list):
            print("Error: Files {} and {} have different number of lines."
                    .format(code_file_name, data_file_name))
            assert False

        for lnum, (comp_fold, data_fold) in enumerate(zip(computed_fold_list, data_fold_list)):
            if comp_fold != data_fold:
                print("        Error: Mismatch of computed value {} and test data value {} on line {} of file {}"
                        .format(comp_fold, data_fold, lnum, data_file_name))
                error_found = True
                #sys.exit(1)
    return error_found

if __name__ == "__main__":

    error_found = test_on_files(verbose=True)
    print()
    print("Tests done and passed." if not error_found else "Tests FAILED")

