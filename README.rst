.. default-role:: code

Cyfolds
=======

Cyfolds is a Vim plugin to calculate syntax-aware folds for Python files.  When
folding the code of functions and classes it leaves the docstring unfolded
along with the top definition line, for a better overview of the module.  The
full file is parsed to find the syntax, so no heuristics are needed.  The
plugin is written in Cython and is compiled to optimized C code for fast
performance.

All the folds are calculated in one pass over the file, and the values are
cached.  The per-buffer cached values are returned if there have been no
changes in the respective buffer since the last call.  See the Cython code file
for more details of the algorithm.

Folding can be customized to occur for various keywords and to change the
number of docstring lines to show.  By default all the text in docstrings is
left unfolded under definitions with the ``def`` or ``class`` keywords.

A screenshot of some example code with folding is shown here:

..  Aligning images: https://gist.github.com/DavidWells/7d2e0e1bc78f4ac59a123ddf8b74932d

.. raw:: html
 
   <p align="center">
   <img src="https://github.com/abarker/cyfolds/blob/master/doc/screenshot_encabulator_reduced.png"
          width="280">
   </p>

Installation
------------

1. When using a plugin manager such as pathogen just clone this GitHub repo
   into the ``bundle`` directory of your ``.vim`` directory.

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
   are Cython and setuptools.  This command will install them:

   .. code-block:: bash

      pip3 install cython setuptools --user --upgrade

4. Now go to the cloned repo and into the ``python3`` directory.   Run the Bash
   script ``compile`` located in that directory.  If you cannot run Bash
   scripts, you can run ``python3 setup.py build_ext --inplace`` directly from
   the command line.

The plugin is now ready to use in Vim.

Configuration
-------------

Turn on folding in Vim, and plugins in general if you haven't already:

.. code-block:: vim

  set foldenable
  filetype plugin on

New key mappings
----------------

In addition to the usual Vim folding keys (see ``:help fold-commands`` in Vim),
Cyfolds adds two new key bindings.

* The ``zuz`` key sequence is used to force the folds to be updated.  (This is
  the same as the FastFolds mapping, but only applies in Python code.)  With
  ``foldmethod`` set to ``manual`` folds always need to be explicitly updated,
  either with ``zuz`` or one of the Vim commands.  When ``foldmethod`` is set
  to ``expr`` folds are updated after inserts but can still get messed up and
  require updating (for example, when deleting characters with ``x`` or lines
  with ``dd``, since those change events do not trigger Vim to update the
  folds).
  
  The ``zuz`` command updates all the folds, returning the folding method to
  whatever method it was set to before the command.  The states of the folds,
  open or closed, are unchanged except for folds created or removed by the
  updating itself.  (This is unlike the built-in ``zx`` and ``zX`` commands,
  which reset the open/closed states of folds.)
  
  This key sequence is mapped to the function call
  ``CyfoldsForceFoldUpdate()``.

* The ``z,`` key sequence toggles the ``foldmethod`` setting between ``expr``
  and ``manual``.  By default Cyfolds starts with the foldmethod set to manual.
  With expr method folds are automatically updated upon leaving insert mode.
  With manual method there is no automatic fold updating; updating must be done
  explicitly, e.g.  with ``zuz``.  Folds are automatically updated upon
  toggling with ``z,``.  The existing folds and their states are left unchanged
  except for changes due to the update operation itself.
  
  The manual foldmethod is best for doing heavy, fast editing with a lot of
  switching in and out of insert mode.  With the expr method there can be a
  small but noticeable delay in quickly moving in and out of insert mode,
  depending on the editing speed and the computer's speed.
  
  This key sequence is mapped to the function call
  ``CyfoldsToggleManualFolds()``.

Settings
--------

Keywords to fold under
~~~~~~~~~~~~~~~~~~~~~~

You can define which particular keywords have folds after them by setting this
configuration variable:

.. code-block:: vim

   let cyfolds_fold_keywords = 'class,def,async def'

The default values are shown.  For Cython, for example, you can set it to:

.. code-block:: vim

   let cyfolds_fold_keywords = 'class,def,async def,cclass,cdef,cpdef'

Any keyword which starts a line and where the statement ends in a colon
can be used.  The list of all of them in Python is:

.. code-block:: vim

   'class,def,async def,while,for,if,else,elif,with,try,except,finally'

If a docstring appears immediately after any such definition it will remain
unfolded just under the opening statement.  This list can be reset dynamically
by passing the new list to the function
``CyfoldsSetFoldKeywords(keyword_str)``.

Number of docstring lines left unfolded
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The number of lines to keep unfolded in module docstrings (and other
freestanding docstrings) can be set by a command such as:

.. code-block:: vim

   let cyfolds_lines_of_module_docstrings = -1

The default value -1 never folds module docstrings.  Nonnegative numbers
keep that many lines open, not including the last line which is never
folded.

The number of lines to keep unfolded in docstrings under keywords such as
``def`` and ``class`` can be set by a command such as:

.. code-block:: vim

   let cyfolds_lines_of_fun_and_class_docstrings = -1

The default value of -1 keeps the full docstring unfolded while the
function or class code just below it is folded.

Other settings
~~~~~~~~~~~~~~

* To fix syntax highlighting on all updates, from the start of the file,
  use this:

  .. code-block:: vim

     let cyfolds_fix_syntax_highlighting_on_update = 1

  The default is not to fix highlighting on all updates.

* This command will change the default of Cyfolds starting with ``foldmethod=manual`` to
  starting with ``foldmethod=expr``:

  .. code-block:: vim

     let cyfolds_start_in_manual_mode = 0

* To disable loading of the Cyfolds plugin use this in your ``.vimrc``:

  .. code-block:: vim

     let cyfolds = 0

* Cyfolds turns off folding in insert mode and restores it on leaving insert
  mode.  This is because in insert mode Vim updates the folds on every character,
  which is slow.  It is also necessary for using the undotree to detect file
  changes, since the updates need to be made after leaving insert mode.

  There is an option to switch the change-detection method to a Python hash of
  the buffer (though it is not recommended if the default method is working):

  .. code-block:: vim

     let cyfolds_hash_for_changes = 1

Sample settings
---------------

In Vim folding the ``foldlevel`` setting determines which folds are open by
default and which are closed.  Any folds with a level less than ``foldlevel``
are open by default.  So when ``foldlevel`` equals 0 all folds are closed by
default, and when it equals 99 all folds are open by default.  The
``foldlevel`` value is increased by the Vim commands ``zr`` and ``zR`` (
**r**\ educe folding), and decreased by the commands ``zm`` and ``zM`` (**m**\ ore
folding).  The ``foldlevelstart`` setting is used to set the initial foldlevel
when files are opened.

Cyfolds always sets the foldlevels of folded lines to the indent level divided
by the shiftwidth (except for freestanding docstrings, where folds have one
added to that value).  So the lines at the first level of indent always have
foldlevel 0, foldable lines on the second level of indent have foldlevel 1,
etc.  Setting ``foldlevel`` to 1, for example, will by default keep all folds
for class and function definitions at the first indent level (0) open and close
all the folds at higher indent levels (such as the methods of a 0-level class).
Setting ``foldlevel`` to 2 will by default keep foldable lines at the first and
second level of indent unfolded by default, and so forth.  The same holds true
for indents due to keywords like, say, ``with`` which are not set to be folded.
For consistency the folds inside them are nevertheless at the higher foldlevel.  

These are the ``.vimrc`` settings I'm currently using:

.. code-block:: vim

   " Cyfolds settings.
   let cyfolds = 1 " Enable or disable loading the plugin.
   "let cyfolds_fold_keywords = "class,def,async def,cclass,cdef,cpdef" " Cython.
   let cyfolds_fold_keywords = "class,def,async def" " Python default.
   let cyfolds_lines_of_module_docstrings = 20 " Lines to keep unfolded, -1 means keep all.
   let cyfolds_lines_of_fun_and_class_docstrings = -1 " Lines to keep, -1 means keep all.
   let cyfolds_start_in_manual_mode = 1 " Default is to start in manual mode.
   let cyfolds_fix_syntax_highlighting_on_update = 1 " Redo syntax highlighting on all updates.

   " General folding settings.
   set foldenable " Enable folding (and instantly close all folds below foldlevel).
   "set nofoldenable " Disable folding (and instantly open all folds).
   set foldcolumn=0 " The width of the fold-info column on the left, default is 0
   set foldlevelstart=-1 " The initial foldlevel; 0 closes all, 99 closes none, -1 default.
   set foldminlines=0 " Minimum number of lines in a fold; don't fold small things.
   "set foldmethod=manual " Set for other file types if desired; Cyfolds ignores it for Python.

Sometimes opening visible folds with a higher fold level can take several
applications of the ``zo`` or ``za`` command.  To force such folds to open or
close immediately I define a fold-toggling function and bind it to the space
bar key (alternately, ``za`` could be remapped):

.. code-block:: vim

   function! SuperFoldToggle()
       " Force the fold under to cursor to immediately open or close.  Unlike za
       " it only takes one application to open any fold.  Unlike zO it does not
       " open recursively, it only opens the current fold.
       if foldclosed('.') == -1
           silent! foldclose
       else 
           while foldclosed('.') != -1
               silent! foldopen
           endwhile
       endif
   endfunction

   " This sets the space bar to toggle folding and unfolding.
   nnoremap <silent> <space> :call SuperFoldToggle()<CR>

While generally not recommended unless you have a very fast computer, Cyfolds
with the setting below, along with the expr folding method, gives the ideal
folding behavior.  It resets the folds after any changes to the text, such as
from deleting and undoing, and after any inserts.  Unfortunately it tends to be
too slow to use with, for example, repeated ``x`` commands to delete words and
repeated ``u`` commands for multiple undos.

.. code-block:: vim

   " Not recommended in general.
   autocmd TextChanged *.py call CyfoldsForceFoldUpdate()

Finally, many Vim color themes have poor settings for the foldline (the visible
line that appears for closed folds) and the foldcolumn (the optional left-side
gutter that appears when ``foldcolumn`` is set greater than the default value
of 0).  The colors can tend to be glaring and distracting, while I prefer that
the background of the foldline match the normal background.  These are are the
two Vim highlighting settings for folds.  Set your own colors, obviously:

.. code-block:: vim

   " Folding
   " -------
   highlight Folded     guibg=#0e0e0e guifg=Grey30  gui=NONE cterm=NONE
   highlight FoldColumn guibg=#0e0e0e guifg=Grey30  gui=NONE cterm=NONE

Set the ``ctermfg`` and ``ctermbg`` instead of or in addition to ``guifg`` and
``guibg`` if your setup uses those.

Interaction with other plugins
------------------------------

vim-stay
~~~~~~~~

The vim-stay plugin, which persists the state of the folds across Vim
invocations, can be used along with this plugin.

FastFolds
~~~~~~~~~

FastFolds does not seem to interfere with Cyfolds and vice versa outside a
Python buffer, but FastFolds does introduce a very slight delay when opening
and closing folds.  That is because it remaps the folding/unfolding keys to
update all folds each time.  Disabling FastFolds for Python files eliminates
this delay (but also the automatic fold updating on those fold commands).  The
disabling command for a ``.vimrc`` is:

.. code-block:: vim

   let fastfold_skip_filetypes=['python']

