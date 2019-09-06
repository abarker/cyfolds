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

A screenshot of some example code with folding is shown here:

raw

.. raw:: html
   
   <img src="https://github.com/abarker/cyfolds/blob/master/doc/screenshot_encabulator_reduced.png"
          style="margin-left: auto;
                 margin-right: auto;
                "
          width="300">

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

4. Now go to the cloned repo and into the ``python3`` directory.   Run the Bash
   script ``compile`` located in that directory (if you cannot run Bash, you
   can run ``python3 setup.py build_ext --inplace`` directly from the command
   line).

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
folding mode to whatever mode it was in before the command.  The states of the
folds, open or closed, is unchanged except for folds changed by the updating
(unlike the built-in ``zx`` and ``zX`` commands which reset the open/closed
states of folds).  This key sequence is mapped to the function call
``CyfoldsForceFoldUpdate()``.

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

To fix syntax highlighting on all updates, from the start of the file,
use this::

   let g:cyfolds_fix_syntax_highlighting_on_update = 1

The default is not to fix highlighting on all updates.

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

   let g:cyfolds_hash_for_changes = 1

Sample settings
~~~~~~~~~~~~~~~

These are ``.vimrc`` settings I'm currently using.

Cyfolds sets the foldlevels of lines to the indent level divided by the
shiftwidth.  So the first level of indent has foldlevel 0, the second has
foldlevel 1, etc.  Setting the foldlevel to 0 folds everything by default.
Setting ``foldlevel`` to 1, for example, will by default keep all the classes
and function definitions at first indent level (0) open and close all the rest
(such as the methods of the class).  The same holds for things line ``with``
which are not being folded at all.  For consistency the things inside them are
at a higher foldlevel, regardless.  

The ``foldlevel`` is changed by commands like ``zr``, ``zR``, ``zm``, and
``zM``.  The ``foldlevelstart`` setting is used to set the initial foldlevel
when files are opened.

.. code-block:: vim

   " Cyfolds settings.
   let g:cyfolds = 1 " Enable or disable loading the plugin.
   "let g:cyfolds_fold_keywords = "class,def,async def,cclass,cdef,cpdef" " Cython.
   let g:cyfolds_fold_keywords = "class,def,async def" " Python default.
   let g:cyfolds_lines_of_module_docstrings = 20 " Lines to keep unfolded, -1 means keep all.
   let g:cyfolds_lines_of_fun_and_class_docstrings = -1 " Lines to keep, -1 means keep all.
   let g:cyfolds_start_in_manual_mode = 1 " Default is to start in manual mode.
   let g:cyfolds_fix_syntax_highlighting_on_update = 1 " Redo syntax highlighting on all updates.

   " General folding settings.
   set foldenable " Enable folding (and instantly close all folds below foldlevel).
   "set nofoldenable " Disable folding and instantly open all folds.
   set foldcolumn=0 " The width of the fold-info column on the left, default is 0
   set foldlevelstart=-1 " The initial foldlevel; 0 closes all, 99 closes none, -1 default.
   set foldminlines=0 " Minimum number of lines in a fold; don't fold small things.
   "set foldmethod=manual " Set for other file types if desired; Cyfolds ignores it for Python.

I also like to define a fold-toggling function that forces folds open or closed
and bind it to the space bar:

.. code-block:: vim

   function! SuperFoldToggle(lnum)
       " Force the fold under to cursor to immediately open or close.  Unlike za
       " it only takes one application to open any fold.  Unlike zO it does not
       " open recursively, it only opens the current fold.
       if foldclosed('.') == -1
          exe 'silent!norm! zc'
       else 
          exe 'silent!norm! 99zo'
       endif
   endfunction

   " This sets the space bar to toggle folding and unfolding.
   nnoremap <silent> <space> :call SuperFoldToggle(line("."))<CR>

While generally not recommended, the setting below along with the expr method
gives the ideal folding behavior.  It resets the folds after any changes to the
text, such as from deleting and undoing.  Unfortunately it is too slow to use
with, for example, repeated ``x`` commands to delete words and repeated ``u``
commands for multiple undos.

.. code-block:: vim

   " Not recommended in general.
   autocmd TextChanged *.py call CyfoldsForceFoldUpdate()

Interaction with other plugins
------------------------------

vim-stay
~~~~~~~~

The vim-stay plugin, which persists the state of the folds across Vim
invocations, can be used along with this plugin.

FastFolds
~~~~~~~~~

FastFolds does not seem to interfere with Cyfolds, but it does introduce a very
slight delay when opening and closing folds.  That is because FastFolds remaps
the folding/unfolding keys to update all folds each time.  Disabling FastFolds
for Python files eliminates this delay (but also the automatic fold updating on
fold commands).  The disabling command for a ``.vimrc`` is:

.. code-block:: vim

   let g:fastfold_skip_filetypes=['python'] |

