.. default-role:: code

Cyfolds
=======

Cyfolds is a vim plugin to calculate syntax-aware folds for Python files.  When
folding functions or classes it leaves the docstring unfolded for a better
overview of the file.  The full file is parsed to find the syntax.  The plugin
is written in Cython and is compiled to give faster performance.

All the folds are calculated in one pass over the file, and the values are
cached.  The cache values are used if there have been no changes in the file.
See the Cython code file for more details of the algorithm.

Installation
------------

When using a plugin manager like pathogen just clone this directory into the
``bundle`` directory.

Configuration
-------------

Turn on folding in vim.  There are currently no configuration options.

Folding is turned off in insert mode, and updated on leaving insert mode.  This
is because in insert mode vim updates the folds on every character, which is
slow.

The `vim-stay` plugin, which persists
the state of the folds across vim invocations, is recommended to use along with
this plugin. Files open slightly faster since the initial folds are read from the save file.

