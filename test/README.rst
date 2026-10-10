Testing Directory
=================

Run the tests with pytest, from this directory or the repo's root directory::

   pytest

The tests in ``test_folds.py`` check the pure-Python ``pyfolds`` module and the
compiled ``cyfolds`` module (skipped if not compiled).  They compare the folds
with the saved data in the ``.testdata`` files, test specific bugs and
settings, and check that the two modules give identical folds.  The tests in
``test_vim.py`` run the plugin in a headless Vim (skipped if no Vim with Python
3 support is found).

To generate test data, run ``generate_folding_testdata_files.py file1.py
file2.py ...`` for the test files.  Each file gets a corresponding ``.testdata``
file, which ``test_folds.py`` automatically uses.

The ``run_with_mocked_vim.py`` module runs the compiled module with a mock Vim,
only testing the generated folds (i.e., not anything having to do with the
functioning of Vim itself).  The ``run_pure_python_version_with_mocked_vim.py``
module does the same for the pure-Python module.
