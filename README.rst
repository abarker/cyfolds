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

The Cython code needs to be compiled before use.  Go to the cloned repo and
into the ``python3`` directory.   Run the Bash script ``compile`` that is in
that directory (if you cannot run Bash, you can run ``python3 setup.py
build_ext --inplace`` directly from the command line).

Configuration
-------------

Turn on folding in vim.  There are currently no configuration options.

Folding is turned off in insert mode, and updated on leaving insert mode.  This
is because in insert mode vim updates the folds on every character, which is
slow.

The vim-stay plugin, which persists the state of the folds across vim
invocations, can be used along with this plugin.

If you use the FastFolds plugin, consider turning it off for Python files when
using Cyfolds.  This is because FastFolds remaps the folding keys to call
update each time, which can cause a slight lag in the time to open and close a
fold.  The command is::

   let g:fastfold_skip_filetypes=['python']

