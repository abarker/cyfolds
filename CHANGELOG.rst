History
=======

2026-10-10
----------

Added a pure-Python version, ``pyfolds.py``, which is used automatically when
the Cython version is not compiled for Vim's Python version.

Fixed the Cython version for Cython 3, where it failed inside Vim.  The Cython
version is also about twice as fast as before.

Bug fixes:

* Indents which are not multiples of ``shiftwidth`` (such as three spaces)
  could end folds early.
* Triple-quoted strings starting a line inside brackets were treated as
  docstrings, causing extra folds or an exception when
  ``g:cyfolds_lines_of_module_docstrings`` was set.
* Braces were not counted as nesting.
* An empty body after a fold keyword could start a fold on a later line.
* With ``g:cyfolds_increase_toplevel_non_class_foldlevels`` set, class methods
  also got the extra foldlevel.

2020-07-30
----------

Added new global variable ``g:cyfolds_increase_toplevel_non_class_foldlevels``.

2019-07-15
----------

Added new global variable ``g:cyfolds_update_all_windows_for_buffer``.
The way that fold updates are forced was rewritten to use ``windo``.

2019-??-??)
-----------

New features:

* None.

Changes:

* None

Bug fixes:

* None

