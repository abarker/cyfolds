" This file contains the vim code for Cyfolds.  It does some one-time
" initialization and then defines the function which will be set as the
" foldeval value to compute the foldlevels.

if !exists('g:cyfolds')
   let g:cyfolds = 1
endif

if exists('g:loaded_cyfolds') || &cp || g:cyfolds == 0
    finish
endif
let g:loaded_cyfolds = 1


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
"let g:pyfoldlevel = '' " Global var for return value of Python function.
if !exists("g:hash_for_changes")
    let g:hash_for_changes = 0
endif

python3 << ----------------------- PythonCode ----------------------------------
"""Python initialization code.  Import the function get_foldlevel."""
import sys
from os.path import normpath, join
import vim

# Put vim python3 directory on sys.path so the plugin can be imported.
vimhome = vim.eval("vimhome")
python_root_dir = normpath(join(vimhome, 'python3'))
sys.path.insert(0, python_root_dir)

from cyfolds import get_foldlevel, delete_buffer_cache
----------------------- PythonCode ----------------------------------


" ==============================================================================
" ==== Define the function GetPythonFoldViaCython, set as foldexpr. ============
" ==============================================================================

function! GetPythonFoldViaCython(lnum)
    " This fun is evaluated for each line and returns the folding level.
    " https://candidtim.github.io/vim/2017/08/11/write-vim-plugin-in-python.html
    " How to return Python values back to vim: https://stackoverflow.com/questions/17656320/
    "echom "Entering GetPythonFoldViaCython..................................." . a:lnum

python3 << ----------------------- PythonCode ----------------------------------
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
----------------------- PythonCode ----------------------------------

    "echom "Returning foldlevel " . g:pyfoldlevel
    return g:pyfoldlevel

endfunction


function! DeleteBufferCache(buffer_num)
" Free the cache memory when a buffer is deleted.
python3 << ----------------------- PythonCode ----------------------------------
buffer_num = int(vim.eval("a:buffer_num"))
delete_buffer_cache(buffer_num)
----------------------- PythonCode ----------------------------------
endfunction

" Call the delete function when the BufDelete event happens.
autocmd BufDelete *.py call DeleteBufferCache(expand('<abuf>'))


" ==============================================================================
" ==== Turn off fold updating in insert mode, and update after TextChanged.  ===
" ==============================================================================

let b:suppress_insert_mode_switching = 0

"augroup unset_python_folding_in_insert_mode
"    autocmd!
"    "autocmd InsertEnter *.py setlocal foldmethod=marker " Bad: opens all folds.
"    autocmd InsertEnter *.py setlocal foldmethod=manual
"    autocmd InsertLeave *.py setlocal foldmethod=expr
"augroup END
"
"augroup unset_cython_folding_in_insert_mode
"    autocmd!
"    autocmd InsertEnter *.pyx setlocal foldmethod=manual
"    autocmd InsertLeave *.pyx setlocal foldmethod=expr
"augroup END

augroup unset_python_folding_in_insert_mode
    autocmd!
    "autocmd InsertEnter *.py setlocal foldmethod=marker " Bad: opens all folds.
    autocmd InsertEnter *.py if b:suppress_insert_mode_switching == 0 | setlocal foldmethod=manual | endif
    autocmd InsertLeave *.py if b:suppress_insert_mode_switching == 0 | setlocal foldmethod=expr | endif
augroup END

augroup unset_cython_folding_in_insert_mode
    autocmd!
    autocmd InsertEnter *.pyx if b:suppress_insert_mode_switching == 0 | setlocal foldmethod=manual | endif
    autocmd InsertLeave *.pyx if b:suppress_insert_mode_switching == 0 | setlocal foldmethod=expr | endif
augroup END

"" Here is a more general form, which preserves the chosen foldmethod.
"augroup unset_folding_in_insert_mode
"    autocmd!
"    autocmd InsertEnter * let b:oldfoldmethod = &l:foldmethod | setlocal foldmethod=manual
"    autocmd InsertLeave * let &l:foldmethod = b:oldfoldmethod
"augroup END


" ==============================================================================
" ==== Force a foldupdate.  ====================================================
" ==============================================================================

function! CyfoldsForceFoldUpdate()
    " Force a fold update.  Unlike zx and zX this does not change the
    " open/closed state of any of the folds.  Can be mapped to a key like 'x,'
    " Could be used inside other commands, but has a little fun-call overhead.
    let l:update_saved_foldmethod = &l:foldmethod
    setlocal foldmethod=manual
    "setlocal foldmethod=expr
    let &l:foldmethod=l:update_saved_foldmethod
endfunction


" ==============================================================================
" ==== Modify foldline to look good with folded Python. ========================
" ==============================================================================

set foldtext=CyfoldsFoldText()
function! CyfoldsFoldText()
    let num_lines = v:foldend - v:foldstart + 1
    let line = getline(v:foldstart)
    let line_indent = indent(v:foldstart-1)
    let sub = substitute(line, '/\*\|\*/\|{{{\d\=', '', 'g')
    return repeat(' ', line_indent) . '+---- ' . num_lines . ' lines ' . v:folddashes
endfunction


" ==============================================================================
" ==== Remap some commands to more convenient forms.============================
" ==============================================================================

"foldclosed(lnum)   " returns first line in range that is closed, else -1
"foldclosed(line("."))
"noremap <F1> :execute "normal! i" . ( line(".") + 1 )<cr>

function CyfoldsSuperFoldToggle(lnum)
    " Force the fold under to cursor to immediately open or close.  Unlike za
    " it only takes one application to open any fold.  Unlike zO it does not
    " open recursively, it only opens the current fold.
    if foldclosed('.') == -1
       exe 'silent!norm! zc'
    else 
       exe 'silent!norm! 99zo'
    endif
endfunction

function CyfoldsToggleManualFolds()
   " Toggle folding method between current one and manual.  Useful when
   " editing a lot and the slight delay on leaving insert mode becomes annoying.
   if &l:foldmethod != 'manual'
      let b:oldfoldmethod = &l:foldmethod
      setlocal foldmethod=manual
      let b:suppress_insert_mode_switching = 1
   else
      let &l:foldmethod = b:oldfoldmethod
      let b:suppress_insert_mode_switching = 0
      call CyfoldsForceFoldUpdate()
   endif
   echom "foldmethod=" . &l:foldmethod
endfunction


"nnoremap <silent> z, :call SuperFoldToggle(line("."))<cr>

" Redefine search, maybe open:
" https://stackoverflow.com/questions/54657330/how-to-override-redefine-vim-search-command
"
" something like :g/egg/foldopen
" https://stackoverflow.com/questions/18805584/how-to-open-all-the-folds-containing-a-search-pattern-at-the-same-time
"
