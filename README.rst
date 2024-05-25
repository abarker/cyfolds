.. default-role:: code

Cyfolds
=======

Cyfolds is a Vim plugin to calculate syntax-aware folds for Python files.
While some Python-folding plugins aim to fold as much text as possible, Cyfolds
retains some context around the folds.  In particular, the full function/class
parameter list is always left unfolded and the function/class docstrings can
optionally be left fully or partially unfolded.  This gives something like an
API view of the code.

The plugin is written in Cython and compiles to optimized C code for fast
performance.  The full file is parsed to find the syntax, so no heuristics are
needed and the folding is always computed correctly.

A screenshot of some example code with folding is shown here:

..  Aligning images: https://gist.github.com/DavidWells/7d2e0e1bc78f4ac59a123ddf8b74932d

.. raw:: html
 
   <p align="center">
   <img src="https://github.com/abarker/cyfolds/blob/master/doc/screenshot_encabulator_reduced.png"
          width="500">
   </p>

Folding can be customized to occur for various keywords, and the number of
docstring lines to show can be modified.  By default all the text in docstrings
is left unfolded after definitions with the ``class``, ``def``, or ``async
def`` keywords, and full module doctrings are shown.

Cyfolds turns off folding in insert mode and restores it on leaving insert
mode.  This is because by default, when in insert mode, Vim updates the folds
on every character.  That is slow and is not really needed.

Installation
------------

Cyfolds requires a Vim that is compiled with Python 3 support and timer
support.  It has currently only been compiled and tested on Vim 8.0 and Neovim
0.2.2 on Ubuntu Linux and on Vim 7.4 on Mint Linux.  It should work with any
recent Linux and Vim distribution, as well as on Windows with a recent Vim.

1. If you use the builtin Vim 8 package manager just clone this GitHub repo
   into the appropriate subdirectory of your ``~/.vim/pack`` directory.
   Similarly, if you use pathogen just clone this GitHub repo into the
   ``~/.vim/bundle`` directory.

2. The C code produced by Cython needs to be compiled before use.  In order to
   do this you need to have a C compiler installed.  On Ubuntu or Debian
   systems you can type:

   .. code-block:: bash

      sudo apt-get install build-essential python3-dev

   On Windows the free MinGW compiler is one option.  To install it, see
   https://cython.readthedocs.io/en/latest/src/tutorial/appendix.html.
   For Mac OS X systems the Cython install page suggests Apple's XCode
   compiler: https://developer.apple.com/.

3. After you have the compiler set up, the Python build requirements
   are Cython and setuptools.  This command installs them:

   .. code-block:: bash

      pip install "cython<3.0" setuptools --user --upgrade

   Note that the plugin does not work with Cython 3.0 for some reason.

4. Now change directories and go to the cloned repo and into the ``python3``
   subdirectory.   Run the Python script named ``compile.py`` that is located
   in that directory:
   
   .. code-block:: bash

      python3 ./compile.py
      
   In Linux just `./compile.py` should work.  You can alternately run

   .. code-block:: bash
   
      python3 setup.py build_ext --inplace
      
   directly from the command line.  To modify the compile options, look in the
   ``setup.py`` file.

The plugin is now ready to use in Vim.

Configuration
-------------

Turn on folding in Vim, and plugins in general if you haven't already:

.. code-block:: vim

  set foldenable
  filetype plugin on

Python indentations are assumed to occur at multiples of the value of
the ``shiftwidth`` setting.  Usually ``set shiftwidth=4`` is used for Python code.

These commands can go into your ``.vimrc`` to always be set.  Python files
should then appear in Vim with Cyfolds folding, set to the default parameters.
See below for the available parameter settings and example ``.vimrc`` settings
which provide a good starting point.

New key mappings
----------------

In addition to the usual Vim folding keys (see ``:help fold-commands`` in Vim),
Cyfolds adds two new key bindings:

* The ``zuz`` key sequence is used to force the folds to be updated.  (This is
  the same as the FastFold mapping, but only applies in Python code.)  When
  the ``foldmethod`` is set to ``manual`` folds always need to be explicitly
  updated either with ``zuz`` or one of the Vim commands.  When the
  ``foldmethod`` is set to ``expr`` folds are updated after inserts but can
  still get messed up and require updating (for example, when deleting
  characters with ``x`` or lines with ``dd``, since those change events do not
  trigger Vim to update the folds).
  
  The ``zuz`` command updates all the folds, returning the folding method to
  whatever method it was set to before the command.  The states of the folds,
  open or closed, are unchanged except for folds created or removed by the
  updating itself.  (This is unlike the built-in ``zx`` and ``zX`` commands,
  which always reset the open/closed states of folds according to
  ``foldlevel`` and which do not work with manual foldmethod.)
  
  The ``zuz`` command sets ``foldenable`` locally for the window if it is not
  already set.  The key sequence is mapped to the function call
  ``CyfoldsForceFoldUpdate()``.

* The ``z,`` key sequence toggles the ``foldmethod`` setting between ``expr``
  and ``manual``.  By default Cyfolds starts with the foldmethod set to manual.
  With the expr foldmethod folds are automatically updated upon leaving insert
  mode.  With the manual foldmethod there is no automatic fold updating; all
  updating must be done explicitly, e.g. with ``zuz``.  Folds are automatically
  updated upon toggling to the ``expr`` method, but not on toggling to the
  ``manual`` method.  The existing folds and their states are left unchanged
  except for changes due to the update operation itself.
  
  The manual foldmethod is best for doing heavy, fast editing with a lot of
  switching in and out of insert mode.  With the expr method there can be a
  small but noticeable delay in quickly moving in and out of insert mode,
  depending on the editing speed and the computer's speed.
  
  The ``z,`` command sets ``foldenable`` locally for the window if it is not
  already set.  The key sequence is mapped to the function call
  ``CyfoldsToggleManualFolds()``.

Customizable settings
---------------------

Keywords to trigger folding
~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can define which particular keywords have folds after them by setting this
configuration variable:

.. code-block:: vim

   let cyfolds_fold_keywords = 'class,def,async def'

The default values are shown above.  For Cython folding, for example, you can
set it to:

.. code-block:: vim

   let cyfolds_fold_keywords = 'class,def,async def,cclass,cdef,cpdef'

Any keyword which starts a line and where the statement ends in a colon
can be used.  The list of all such keywords in Python is:

.. code-block:: vim

   'class,def,async def,while,for,if,else,elif,with,try,except,finally'

If a docstring appears immediately after any such definition it will remain
unfolded just under the opening statement.

This list can be reset dynamically (to the new values set in the global
variable) by running ``:call CyfoldsUpdateFoldKeywords()``.

Number of docstring lines left unfolded
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The number of lines to keep unfolded in module docstrings (and other
freestanding docstrings) can be set by a command such as:

.. code-block:: vim

   let cyfolds_lines_of_module_docstrings = -1

The default value -1 always keeps the full module docstring unfolded.
Nonnegative numbers keep that many lines open, not including the last line
which is never folded.

The number of lines to keep unfolded in docstrings under keywords such as
``def`` and ``class`` can similarly be set by a command such as:

.. code-block:: vim

   let cyfolds_lines_of_fun_and_class_docstrings = -1

The default value of -1 keeps the full docstring unfolded while the
function or class code just below it is folded.

Other settings
~~~~~~~~~~~~~~

* This setting will change the default of Cyfolds starting with
  ``foldmethod=manual`` to starting with ``foldmethod=expr``:

  .. code-block:: vim

     let cyfolds_start_in_manual_method = 0

* To disable automatic fold calculations (and initial folding) on opening a
  Python buffer you can use:

  .. code-block:: vim

     let cyfolds_no_initial_fold_calc = 1
 
  This setting is useful if you only sometimes use folds and do not want the
  fold calculations to happen automatically (a very small slowdown on
  startup).  This setting also causes Cyfolds to start with ``foldmethod`` set
  to ``manual``.  To then switch to using folding you need to explicitly force
  the folds to be updated, such as with ``zuz`` or ``z,``.

* To also fix syntax highlighting on all fold updates, from the start of the
  file, use this setting (the default is 0, no syntax fixing):

  .. code-block:: vim

     let cyfolds_fix_syntax_highlighting_on_update = 1

* To increase the foldlevel of all toplevel (module-scope, with indent 0)
  elements except for classes, use:

  .. code-block:: vim

     let cyfolds_increase_toplevel_non_class_foldlevels = 1

  This is nice because when the ``foldlevel`` value is 0 all the module-level
  elements are folded, but when it is 1 all the elements except classes are
  folded.  This puts module-level functions and class methods at the same level
  of folding, which gives a nice API view.  This works well, for example, with
  ``set foldlevelstart=1`` in the ``.vimrc``.  The builtin ``zm`` and ``zr``
  commands can be used to go back and forth between the views.

  The only minor downside is that when ``foldlevel`` is 0 it takes two
  applications of the builtin ``zo`` or ``za`` commands to open folded, toplevel,
  non-class elements.  The ``SuperFoldToggle`` function, described below, does
  not have this problem.

* To define the fold-updating function to update all the windows for the
  current buffer instead of just updating the current window, use:

  .. code-block:: vim

     let cyfolds_update_all_windows_for_buffer = 1

  The default is 0, to only update the folds in the current window.  That is
  essentially what the built-in ``zx`` and ``zX`` commands do.  Updating all
  the windows for the current buffer is convenient when you have multiple
  windows for a buffer.  It is only slightly slower than only updating the
  current buffer (the folds for each such window need to be set, but they only
  need to be calculated once).

* To completely disable loading of the Cyfolds plugin use this in your
  ``.vimrc``:

  .. code-block:: vim

     let cyfolds = 0

Example settings
----------------

In Vim folding the ``foldlevel`` setting determines which folds are open by
default and which are closed.  Any folds with a level less than ``foldlevel``
are open by default.  So when ``foldlevel`` equals 0 all folds are closed by
default, and when it equals 99 all folds are open by default.  The
``foldlevel`` value is increased by the Vim commands ``zr`` and ``zR`` ( **r**\
educe folding), and decreased by the commands ``zm`` and ``zM`` (**m**\ ore
folding).  The ``foldlevelstart`` setting is used to set the initial foldlevel
when files are opened.

Cyfolds sets the foldlevels of folded lines to the indent level divided by the
shiftwidth (except for freestanding docstrings, where folds have one extra
level added to that value).  So the lines at the first level of indent always
have foldlevel 0, foldable lines on the second level of indent have foldlevel
1, etc.  Setting ``foldlevel`` to 1, for example, will keep all folds for class
and function definitions at the first indent level (0) open and close all the
folds at higher indent levels (such as the methods of a class at 0-level).
Setting ``foldlevel`` to 2 will keep foldable lines at the first and second
level of indent unfolded, and so forth.  The same holds true for indents due to
keywords which are not set to be folded (like, say, ``with``).  For consistency
the folds inside them are nevertheless at the higher foldlevel.  

These are the ``.vimrc`` settings I'm currently using:

.. code-block:: vim

   " Cyfolds settings.
   let cyfolds = 1 " Enable or disable loading the plugin.
   "let cyfolds_fold_keywords = "class,def,async def,cclass,cdef,cpdef" " Cython.
   let cyfolds_fold_keywords = "class,def,async def" " Python default.
   let cyfolds_lines_of_module_docstrings = 20 " Lines to keep unfolded, -1 means keep all.
   let cyfolds_lines_of_fun_and_class_docstrings = -1 " Lines to keep, -1 means keep all.
   let cyfolds_start_in_manual_method = 1 " Default is to start in manual mode.
   let cyfolds_no_initial_fold_calc = 0 " Whether to skip initial fold calculations.
   let cyfolds_fix_syntax_highlighting_on_update = 1 " Redo syntax highlighting on all updates.
   let cyfolds_update_all_windows_for_buffer = 1 " Update all windows for buffer, not just current.
   let cyfolds_increase_toplevel_non_class_foldlevels = 0

   " General folding settings.
   set foldenable " Enable folding and show the current folds.
   "set nofoldenable " Disable folding and show normal, unfolded text.
   set foldcolumn=0 " The width of the fold-info column on the left, default is 0
   set foldlevelstart=-1 " The initial foldlevel; 0 closes all, 99 closes none, -1 default.
   set foldminlines=0 " Minimum number of lines in a fold; don't fold small things.
   "set foldmethod=manual " Set for other file types if desired; Cyfolds ignores it for Python.

If you want to define any of the builtin folding settings for Python files
only, assuming they take local values, you could alternately use autocommands
in your ``.vimrc``, calling ``setlocal``.  For example, to start with top-level
functions and classes unfolded, but only in Python files, you could use:

.. code-block:: vim

   autocmd FileType python setlocal foldlevel=1

Sometimes opening visible folds with a higher fold level can take several
applications of the builtin ``zo`` or ``za`` commands.  To force all folds to
open or close immediately I define this fold-toggling function in my ``.vimrc``
file and bind it to the normal-mode space bar key (alternately, ``za`` or any
other key could be remapped):

.. code-block:: vim

   function! SuperFoldToggle()
       " Force the fold on the current line to immediately open or close.  Unlike za
       " and zo it only takes one application to open any fold.  Unlike zO it does
       " not open recursively, it only opens the current fold.
       if foldclosed('.') == -1
           silent! foldclose
       else 
           while foldclosed('.') != -1
               silent! foldopen
           endwhile
       endif
   endfunction

   " This sets the space bar to toggle folding and unfolding in normal mode.
   nnoremap <silent> <space> :call SuperFoldToggle()<CR>

While generally not recommended unless you have a very fast computer, Cyfolds
with the setting below, along with the expr folding method, gives the ideal
folding behavior.  It resets the folds after any changes to the text, such as
from deleting and undoing, and after any inserts.  Unfortunately it can be too
slow to use with, for example, repeated ``x`` commands to delete words and
repeated ``u`` commands for multiple undos.

.. code-block:: vim

   " Not recommended in general.
   autocmd TextChanged *.py call CyfoldsForceFoldUpdate()

Finally, some Vim color themes have poor settings for the foldline (the visible
line that appears for closed folds) and the foldcolumn (the optional left-side
gutter that appears when ``foldcolumn`` is set greater than the default value
of 0).  The colors can sometimes be glaring and distracting.  I prefer the
background of the foldline to match the normal background.  These are the two
Vim highlighting settings for folds.  Use your own colors, obviously:

.. code-block:: vim

   " Folding
   " -------
   highlight Folded     guibg=#0e0e0e guifg=Grey30  gui=NONE cterm=NONE
   highlight FoldColumn guibg=#0e0e0e guifg=Grey30  gui=NONE cterm=NONE

Set the ``ctermfg`` and ``ctermbg`` instead of (or in addition to) ``guifg``
and ``guibg`` if your setup uses those.

Interaction with other plugins
------------------------------

vim-stay
~~~~~~~~

The vim-stay plugin, which persists the state of the folds across Vim
invocations, can be used along with this plugin.

FastFold
~~~~~~~~

FastFold does not seem to interfere with Cyfolds and vice versa outside a
Python buffer.  FastFold with Cyfolds in a Python buffer does introduce a very
slight delay when opening and closing folds.  That is because it remaps the
folding/unfolding keys to update the folds each time.  Disabling FastFold for
Python files eliminates this delay (but also the automatic fold updating on
those fold commands).  Cyfolds handles things like suppressing fold updates in
insert mode and forcing updates (`zuz`) by itself, so turning off FastFold for
Python buffers is recommended.  The FastFold ``.vimrc`` command for that is:

.. code-block:: vim

   let fastfold_skip_filetypes=['python']

