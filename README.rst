.. default-role:: code

Cyfolds
=======

Cyfolds is a Vim plugin to calculate syntax-aware folds for Python files.  When
folding functions or classes it leaves the docstring unfolded for a better
overview of the file.  The full file is parsed to find the syntax, so no
heuristics are needed.  The plugin is written in Cython and is compiled to
optimized C code for fast performance.

All the folds are calculated in one pass over the file, and the values are
cached.  The per-buffer cached values are returned if there have been no
changes in the respective buffer since the last call.  See the Cython code file
for more details of the algorithm.

Folding can be customized to occur for various keywords.  By default docstrings
are folded at the same level as the ``def``, ``class``, or other keyword above
them so they are visible at the same time.

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

The plugin is now ready to use in Vim.

Configuration
-------------

Turn on folding in Vim and plugins in general if you haven't already::

  set foldenable
  filetype plugin on

New key mappings
----------------

Use ``zuz`` to force the folds to be updated (same as the FastFolds mapping,
but only in Python).  In manual mode folds always need to be explicitly
updated.  In expr mode folds can get messed up, for example, when deleting
characters with ``x`` or lines with ``dd`` (those change events do not trigger
Vim to update the folds).  The ``zuz`` command updates the folds, returning the
folding mode to whatever mode it was in before the command.  This key sequence
is mapped to the function call ``CyfoldsForceFoldUpdate()``.

Use ``z,`` to toggle between manual mode and expr mode.  By default Cyfolds
starts in manual mode.  In expr mode folds are automatically updated upon
leaving insert mode.  In manual mode there is no automatic fold updating;
updating must be done explicitly with ``zuz``.  Manual mode is best for heavy,
fast editing with a lot of switching in and out of insert mode.  (In expr mode
heavy editing can be annoying due to the small delay in updating folds.)  Folds
are updated automatically upon toggling.  The existing folds and their states are
left unchanged except for updates.  This key sequence is mapped to the function
call ``CyfoldsToggleManualFolds()``.

Settings
--------

You can define which particular keywords are folded after by setting this
configuration variable::

   let g:cyfolds_fold_keywords = "class,def,async def"

The default values are shown.  For Cython, for example, you can set it to::

   let g:cyfolds_fold_keywords = "class,def,async def,cclass,cdef,cpdef"

Any keyword which starts a line and where the statement ends in a colon
can be used.  The list of all of them in Python is::

   "class,def,async def,while,for,if,else,elif,with,try,except,finally"

If a docstring appears immediately after any such definition it will remain
unfolded just under the opening statement.  This list can be reset dynamically
by passing the new list to the function
``CyfoldsSetFoldKeywords(keyword_str)``.

The number of lines to keep unfolded in module docstrings (and other
freestanding docstrings) can be set by a command such as::

   let g:cyfolds_lines_of_module_docstrings = -1

The default value -1 never folds module docstrings.  Nonnegative numbers
keep that many lines open, not including the last line which is never
folded.

The number of lines to keep unfolded in docstrings under keywords such as
``def`` and ``class`` can be set by a command such as::

   let g:cyfolds_lines_of_fun_and_class_docstrings = -1

The default value of -1 keeps the full docstring unfolded while the
function or class code just below it is folded.

This command will change the default Cyfolds starting mode from manual mode to
expr mode::

   let g:cyfolds_start_in_manual_mode = 0

To disable loading of the Cyfolds plugin use this in your ``.vimrc``::

   let g:cyfolds = 0

Cyfolds turns off folding in insert mode and restores it on leaving insert
mode.  This is because in insert mode Vim updates the folds on every character,
which is slow.  It is also necessary for using the undotree to detect file
changes, since the updates need to be made after leaving insert mode.  There is
an option to switch to using a Python hash to detect changes, by setting::

   g:cyfolds_hash_for_changes=1

Suggested settings
~~~~~~~~~~~~~~~~~~

<copy from .vimrc when good, and colors from color file>

Interaction with other plugins
------------------------------

vim-stay
~~~~~~~~

The vim-stay plugin, which persists the state of the folds across Vim
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

