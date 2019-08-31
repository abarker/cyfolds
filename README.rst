.. default-role:: code

Cyfolds
=======

Cyfolds is a vim plugin to calculate syntax-aware folds for Python files.  When
folding functions or classes it leaves the docstring unfolded for a better
overview of the file.  The full file is parsed to find the syntax, so no
heuristics are needed.  The plugin is written in Cython and is compiled to
optimized C for fast performance.

All the folds are calculated in one pass over the file, and the values are
cached.  The per-buffer cached values are used if there have been no changes in
the respective buffer since the last call.  See the Cython code file for more
details of the algorithm.

Installation
------------

When using a plugin manager like pathogen just clone this directory into the
``bundle`` directory.

The Cython code needs to be compiled before use.  The Python build requirements
are cython and setuptools.  This command will install them::

   pip3 install cython setuptools --user

Go to the cloned repo and into the ``python3`` directory.   Run the Bash script
``compile`` that is in that directory (if you cannot run Bash, you can run
``python3 setup.py build_ext --inplace`` directly from the command line).

Configuration
-------------

Turn on folding in vim and plugins in general if you haven't already::

  set foldenable
  filetype plugin on

New commands
~~~~~~~~~~~~

Use ``zuz`` to force the folds to be updated (same as the FastFolds mapping,
but only in Python).  Folds can get messed up, for example, when deleting
characters with ``x`` or lines with ``dd``.  This happens because those change
events do not trigger vim to update the folds.

Use ``z,`` to pause the regular (expr) mode and go to manual mode.  When in
manual mode there is no fold updating, including on leaving insert mode (the
small delay there can be annoying during heavy editing).  To toggle regular
mode back on hit ``z,`` again.  Folds are updated automatically upon toggling
back.  The existing folds and their states are left unchanged.

Settings
~~~~~~~~

You can define which particular keywords are folded after by setting this
configuration variable::

   let g:cyfolds_fold_keywords = "class,def,async def"

The default values are shown.  For Cython you can set it to::

   let g:cyfolds_fold_keywords = "class,def,async def,cclass,cdef,cpdef"

Any keyword which starts a line and where the statement ends in a colon
can be used.  The list of all of them in Python is::

   "class,def,async def,while,for,if,else,elif,with,try,except,finally"

If a docstring appears immediately after any such definition it will remain
unfolded along with the main statement.  This list can be reset dynamically
by passing the new list to the function ``CyfoldsSetFoldKeywords``.

To disable loading of the Cyfolds plugin use this in your ``.vimrc``::

   let g:cyfolds = 0

To suppress switching fold updates off in insert mode (not recommended)::

   let g:suppress_insert_mode_switching = 1

Cyfolds turns off folding in insert mode and restores it on leaving insert
mode.  This is because in insert mode vim updates the folds on every character,
which is slow.  It is also necessary for using the undotree to detect file
changes since the updates need to be made after leaving insert mode.  There is
an option to switch to using a Python hash to detect changes, by setting::

   g:hash_for_changes=1

Suggested settings
~~~~~~~~~~~~~~~~~~

<copy from .vimrc when good, and colors from color file>

Interaction with other plugins
------------------------------

vim-stay
~~~~~~~~

The vim-stay plugin, which persists the state of the folds across vim
invocations, can be used along with this plugin.

FastFolds
~~~~~~~~~

If you use the FastFolds plugin, consider turning it off for Python files when
using Cyfolds.  This is because FastFolds remaps the folding keys to call
update each time, which can cause a slight lag in the time to open and close a
fold.  The command is::

   let g:fastfold_skip_filetypes=['python']

