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

1. When using a plugin manager such as pathogen just clone this GitHub repo
   into the ``bundle`` directory of your ``.vim`` directory.

2. The C code produced by Cython needs to be compiled before use.  In order to
   do this you need to have a C compiler installed.  On Ubuntu or Debian
   systems you can type::

      sudo apt-get install build-essential

   On Windows the free MinGW compiler is one option.  To install it, see
   https://cython.readthedocs.io/en/latest/src/tutorial/appendix.html.
   For Mac OS X systems the Cython install page suggests Apple's XCode
   compiler: https://developer.apple.com/.

3. After you have the compiler set up, the Python build requirements
   are Cython and setuptools.  This command will install them::

      pip3 install cython setuptools --user --upgrade

4. Now go to the cloned repo and into the ``python3`` directory.   Run the Bash script
   ``compile`` located in that directory (if you cannot run Bash, you can run
   ``python3 setup.py build_ext --inplace`` directly from the command line).

The plugin is now ready to use in vim.

Configuration
-------------

Turn on folding in vim and plugins in general if you haven't already::

  set foldenable
  filetype plugin on

New commands
------------

Use ``z,`` to pause the regular (expr) mode and go to manual mode.  When in
manual mode there is no fold updating, including on leaving insert mode (the
small delay there can be annoying during heavy, fast editing).  To toggle back
to regular mode hit ``z,`` again.  Folds are updated automatically upon
toggling back.  The existing folds and their states are left unchanged.  In
manual mode you can hit ``z,`` twice to force a fold update and return to mode.
This command is mapped to the function call ``CyfoldsToggleManualFolds()``.

Use ``zuz`` to force the folds to be updated (same as the FastFolds mapping,
but only in Python).  Folds can get messed up, for example, when deleting
characters with ``x`` or lines with ``dd``.  This happens because those change
events do not trigger vim to update the folds.  This command always switches
back to regular (expr) mode.  Use ``z,`` to return to manual mode.  This
command is mapped to the function call ``CyfoldsForceFoldUpdate()``.

Settings
--------

You can define which particular keywords are folded after by setting this
configuration variable::

   let g:cyfolds_fold_keywords = "class,def,async def"

The default values are shown.  For Cython you can set it to::

   let g:cyfolds_fold_keywords = "class,def,async def,cclass,cdef,cpdef"

Any keyword which starts a line and where the statement ends in a colon
can be used.  The list of all of them in Python is::

   "class,def,async def,while,for,if,else,elif,with,try,except,finally"

If a docstring appears immediately after any such definition it will remain
unfolded just under the opening statement.  This list can be reset dynamically
by passing the new list to the function
``CyfoldsSetFoldKeywords(keyword_str)``.

To disable loading of the Cyfolds plugin use this in your ``.vimrc``::

   let g:cyfolds = 0

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
fold.  It also redefines ``zuz``, and its mechanism to switch off in insert
mode might conflict with Cyfolds.  The full command for a ``.vimrc`` is::

   autocmd <silent> filetype python
                          \ let g:fastfold_skip_filetypes=['python'] |
                          \ nmap <SID>(DisableFastFoldUpdate) <Plug>(FastFoldUpdate) |
                          \ let g:fastfold_savehook = 0

Note that this only applies to Python files.

