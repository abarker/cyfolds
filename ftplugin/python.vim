
" ==============================================================================
" ==== Python version, set up call to the Python script ========================
" ==============================================================================

setlocal foldmethod=expr
setlocal foldexpr=GetPythonFoldPython(v:lnum)

function! GetPythonFoldPython(lnum)
" This fun is evaluated for each line, tells folding level.
" https://candidtim.github.io/vim/2017/08/11/write-vim-plugin-in-python.html
" How to return Python values back to vim: https://stackoverflow.com/questions/17656320/

   if has('win32') || has ('win64')
      let vimhome = $VIM."/vimfiles"
   else
      let vimhome = $HOME."/.vim"
   endif

   let g:pyfoldlevel = '' " Global var for return value.

python3 << ---------------------------PythonCode----------------------------------

import sys
from os.path import normpath, join
import vim

# Put vim python3 directory on sys.path so the plugin can be imported.
vimhome = vim.eval("vimhome")
python_root_dir = normpath(join(vimhome, 'python3'))
sys.path.insert(0, python_root_dir)

from cyfolds import get_foldlevel

# Set some Python variables from vim ones, to pass to get_foldlevel.
lnum = vim.eval("a:lnum")
shiftwidth = vim.eval("&shiftwidth")
foldnestmax = vim.eval("&foldnestmax")

# Call the Python/Cython function to do the computation.
computed_foldlevel = get_foldlevel(lnum, foldnestmax, shiftwidth)

# Set the return value as a global vim variable, to pass it back to vim.
vim.command("let g:pyfoldlevel = {}".format(computed_foldlevel))

---------------------------PythonCode----------------------------------

   return g:pyfoldlevel

endfunction

" ==============================================================================
" ==== unset folding in insert mode ============================================
" ==============================================================================

augroup unset_folding_in_insert_mode
    autocmd!
    "autocmd InsertEnter *.py setlocal foldmethod=marker " Bad: opens all folds.
    autocmd InsertEnter *.py setlocal foldmethod=manual
    autocmd InsertLeave *.py setlocal foldmethod=expr
augroup END

" ==============================================================================
" ==== modify foldline =========================================================
" ==============================================================================

set foldtext=CyfoldFoldText()
function CyfoldFoldText()
   let num_lines = v:foldend - v:foldstart + 1
   let line = getline(v:foldstart)
   let line_indent = indent(v:foldstart-1)
   let sub = substitute(line, '/\*\|\*/\|{{{\d\=', '', 'g')
   return repeat(" ", line_indent) . "+---- " . num_lines . " lines " . v:folddashes
endfunction

