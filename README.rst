.. default-role:: code

pytest-helper
=============

The pytest-helper package allows modules, both inside and outside of packages,
to be made self-testing with `pytest <http://pytest.org>`_ when the module
itself is executed as a script.  The test functions that are run can be in the
same module or they can be in a module in a separate test directory.
Standalone testing modules can also set up so that pytest actually runs them
when they are executed.

Several additional utility functions are provided to make it easier to set up
and run unit tests.  For example, there is a function to simplify making
modifications to the Python search path so tests are discovered.  One of the
useful features of the package is that relative pathnames are always
interpreted relative to the directory of the file in which they occur (i.e.,
not relative to the Python CWD which can vary depending on how the python
interpreter is invoked).

For examples and full documentation, see https://abarker.github.io/pytest-helper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The easiest way to install is to install from PyPI using pip:

.. code-block:: bash

   pip install pytest-helper

