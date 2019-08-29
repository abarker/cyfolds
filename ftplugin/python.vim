" This file contains the vim code for Cyfolds.  It does some one-time
" initialization and then defines the function which will be set as the
" foldeval value to compute the foldlevels.


" ==============================================================================
" ==== Initialization. =========================================================
" ==============================================================================

setlocal foldmethod=expr
setlocal foldexpr=GetPythonFoldViaCython(v:lnum)

if has('win32') || has ('win64')
   let vimhome = $VIM."/vimfiles"
else
   let vimhome = $HOME."/.vim"
endif

" When multiple open view windows are used and you first open
" pratt_constructs.py and then pratt_parser.py in another, it uses the
" folds for pratt_constructs.py for pratt_parser.py, AND it is very slow
" and seems to recompute each time, caching fail.  But only intermittently.
" It seems like the buffer passed in may not yet be set to the new buffer
" in some cases, maybe????????????????  Even with caching based on hashing.
" Define class egg, then it folds, then delete def line with dd... fold
" remains.
"let g:hash_for_changes = 1 " debugging only
let g:pyfoldlevel = '' " Global var for return value.
if !exists("g:hash_for_changes")
   let g:hash_for_changes = 0
endif

python3 << =========================== PythonCode ==================================
"""Python initialization code.  Import the function get_foldlevel."""
import sys
from os.path import normpath, join
import vim

# Put vim python3 directory on sys.path so the plugin can be imported.
vimhome = vim.eval("vimhome")
python_root_dir = normpath(join(vimhome, 'python3'))
sys.path.insert(0, python_root_dir)

from cyfolds import get_foldlevel, delete_buffer_cache
=========================== PythonCode ==================================


" ==============================================================================
" ==== Define the function GetPythonFoldViaCython, set as foldexpr. ===============
" ==============================================================================

function! GetPythonFoldViaCython(lnum)
   " This fun is evaluated for each line and returns the folding level.
   " https://candidtim.github.io/vim/2017/08/11/write-vim-plugin-in-python.html
   " How to return Python values back to vim: https://stackoverflow.com/questions/17656320/
   "echom "Entering GetPythonFoldViaCython..................................." . a:lnum

python3 << =========================== PythonCode ==================================
"""Python code that calls the Cython function get_foldlevel and returns the
foldlevel in the global variable pyfoldlevel."""

# Set some Python variables from vim ones, to pass as args to get_foldlevel.
lnum = int(vim.eval("a:lnum"))
shiftwidth = int(vim.eval("&shiftwidth"))
foldnestmax = int(vim.eval("&foldnestmax"))
cur_buffer_num = int(vim.eval("bufnr('%')"))
hash_for_changes = int(vim.eval("g:hash_for_changes"))
if hash_for_changes:
   cur_undo_sequence = None
else:
    cur_undo_sequence = vim.eval("undotree().seq_cur")

# Call the Cython function to do the computation.
computed_foldlevel = get_foldlevel(lnum, cur_buffer_num, cur_undo_sequence,
                                   foldnestmax, shiftwidth)

# Set the return value as a global vim variable, to pass it back to vim.
vim.command("let g:pyfoldlevel = {}".format(computed_foldlevel))
=========================== PythonCode ==================================

   "echom "Returning foldlevel " . g:pyfoldlevel
   return g:pyfoldlevel

endfunction


function! DeleteBufferCache(buffer_num)
" Free the cache memory when a buffer is deleted.
python3 << =========================== PythonCode ==================================
buffer_num = int(vim.eval("a:buffer_num"))
delete_buffer_cache(buffer_num)
=========================== PythonCode ==================================
endfunction

" Call the delete function when the BufDelete event happens.
autocmd BufDelete *.py call DeleteBufferCache(expand('<abuf>'))

" ==============================================================================
" ==== Turn off fold updating in insert mode, and update after TextChanged.  ===
" ==============================================================================

augroup unset_folding_in_insert_mode
    autocmd!

    " Python.
    "autocmd InsertEnter *.py setlocal foldmethod=marker " Bad: opens all folds.
    autocmd InsertEnter *.py setlocal foldmethod=manual
    autocmd InsertLeave *.py setlocal foldmethod=expr

    " Cython.
    autocmd InsertEnter *.pyx setlocal foldmethod=manual
    autocmd InsertLeave *.pyx setlocal foldmethod=expr
augroup END

" This updates (all) the folds only in normal mode, on a delete, undo, etc.
autocmd TextChanged *.py setlocal foldmethod=manual | setlocal foldmethod=expr

"" Here is a more general form, which preserves the chosen foldmethod.
"augroup unset_folding_in_insert_mode
"    autocmd!
"    autocmd InsertEnter * let b:oldfoldmethod = &l:foldmethod | setlocal foldmethod=manual
"    autocmd InsertLeave * let &l:foldmethod = b:oldfoldmethod
"augroup END


" ==============================================================================
" ==== Modify foldline to look good with folded Python.  =======================
" ==============================================================================

set foldtext=CyfoldFoldText()
function! CyfoldFoldText()
   let num_lines = v:foldend - v:foldstart + 1
   let line = getline(v:foldstart)
   let line_indent = indent(v:foldstart-1)
   let sub = substitute(line, '/\*\|\*/\|{{{\d\=', '', 'g')
   return repeat(" ", line_indent) . "+---- " . num_lines . " lines " . v:folddashes
endfunction


