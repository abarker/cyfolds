" This file contains the Vim code for Cyfolds.  It does some one-time
" initialization and then defines the function which will be set as the
" foldeval value to compute the foldlevels.
"
"==============================================================================
" This file is part of the Cyfolds package, Copyright (c) 2019 Allen Barker.
" License details (MIT) can be found in the file LICENSE.
"==============================================================================

if exists("b:did_ftplugin")
   finish
endif
let b:did_ftplugin = 1

let s:cpo_save = &cpo
set cpo&vim " No vim compatible mode; reset cpo to vim default.

if !exists('g:cyfolds')
   let g:cyfolds = 1
endif

if exists('g:loaded_cyfolds') || &cp || g:cyfolds == 0
    finish " Don't run if already loaded or user set g:cyfolds=0.
endif
let g:loaded_cyfolds = 1

let b:undo_ftplugin = "setl foldmethod< foldtext< foldexpr< foldenable< ofu<"
                  \ . "| unlet! b:match_ignorecase b:match_words b:suppress_insert_mode_switching"
                  \ . " b:insert_saved_foldmethod b:update_saved_foldmethod"

" What is the overhead of calling Python from Vim?  The cached foldlevel
" values could be stored in a Vim list, which would eliminate the need to call
" Python except to fill the list on dirty cache.  Would that make any
" significant difference in speed?  Dirty cache detection would necessarily
" need to be via undotree data.
"
" See vim.List in :h python-bindeval-objects
" Maybe something like
"    cyfolds_foldlevel_cache = vim.bindeval('g:cyfolds_foldlevel_cache')
"
" Downside is bindeval is only in newer Vims, and apparently not
" compatible with neovim: https://github.com/neovim/neovim/issues/1898

" ==============================================================================
" ==== Initialization. =========================================================
" ==============================================================================

let s:timer_wait = 500 " Timer wait in milliseconds, time before switch to manual.

if has('win32') || has ('win64')
    let s:vimhome = $VIM."/vimfiles"
else
    let s:vimhome = $HOME."/.vim"
endif

if !exists("g:cyfolds_hash_for_changes")
    let g:cyfolds_hash_for_changes = 0
endif

if !exists("g:cyfolds_fold_keywords")
    let g:cyfolds_fold_keywords = "class,def,async def"
endif

if !exists("g:cyfolds_start_in_manual_method")
    let g:cyfolds_start_in_manual_method = 1
endif

if !exists("g:cyfolds_lines_of_module_docstrings")
    let g:cyfolds_lines_of_module_docstrings = -1
endif

if !exists("g:cyfolds_lines_of_fun_and_class_docstrings")
    let g:cyfolds_lines_of_fun_and_class_docstrings = -1
endif

if !exists("g:cyfolds_fix_syntax_highlighting_on_update")
    let g:cyfolds_fix_syntax_highlighting_on_update = 0
endif

if !exists("g:cyfolds_no_initial_fold_calc")
    let g:cyfolds_no_initial_fold_calc = 0
endif


function! CyfoldsBufEnterInit()
    " Initialize upon entering a buffer.

    if g:cyfolds_no_initial_fold_calc != 1
        setlocal foldmethod=expr
    else
        setlocal foldmethod=manual
    endif

    setlocal foldexpr=GetPythonFoldViaCython(v:lnum)
    setlocal foldtext=CyfoldsFoldText()

    " Map the keys zuz and z, to their commands.
    nnoremap <buffer> <silent> zuz :call CyfoldsForceFoldUpdate()<CR>
    nnoremap <buffer> <silent> z, :call CyfoldsToggleManualFolds()<CR>

    " Initialize variables.
    let b:suppress_insert_mode_switching = 0

    " Start with the chosen foldmethod.
    if g:cyfolds_start_in_manual_method == 1 && &foldmethod != 'manual'
        call DelayManualMethod()
    endif
endfunction

augroup cyfolds_buf_new_init
    " Using BufWinEnter, but BufEnter event seems to work, too; not sure which
    " is best or if it matters.  BufNew and BufAdd don't work.
    autocmd!
    "autocmd BufEnter *.py,*.pyx,*.pxd :call CyfoldsBufEnterInit()
    autocmd BufWinEnter *.py,*.pyx,*.pxd :call CyfoldsBufEnterInit()
augroup END


python3 << ----------------------- PythonCode ----------------------------------
"""Python initialization code.  Import the function call_get_foldlevel."""
import sys
from os.path import normpath, join
import vim

import cyfolds
# These vars are set in cyfolds.py to try to accomodate slowness issues when in Neovim.
# https://github.com/neovim/neovim/issues/7063
vim_eval = cyfolds.vim_eval
#vim_command = cyfolds.vim_command
#vim_current_buffer = cyfolds.vim_current_buffer

# Put vim python3 directory on sys.path so the plugin can be imported.
vimhome = vim_eval("s:vimhome")
cyfolds_fold_keywords = vim_eval("cyfolds_fold_keywords")
python_root_dir = normpath(join(vimhome, 'python3'))
sys.path.insert(0, python_root_dir)

from cyfolds import delete_buffer_cache, setup_regex_pattern, call_get_foldlevels
setup_regex_pattern(cyfolds_fold_keywords)
----------------------- PythonCode ----------------------------------


" ==============================================================================
" ==== Define the function GetPythonFoldViaCython to be set as foldexpr.========
" ==============================================================================

function! GetPythonFoldViaCython(lnum)
    " This function is evaluated for each line and returns the folding level.
    " https://candidtim.github.io/vim/2017/08/11/write-vim-plugin-in-python.html
    " How to return Python values back to vim: https://stackoverflow.com/questions/17656320/
    " TODO: Is there a way to define dirty cache function in vimscript, to
    " check here before calling the function (which is expensive in nvim)?
    if a:lnum == 1
       python3 call_get_foldlevels()
    endif
    return b:cyfolds_foldlevel_array[a:lnum-1]
endfunction

function! DeleteBufferCache(buffer_num)
" Free the cache memory when a buffer is deleted.
python3 << ----------------------- PythonCode ----------------------------------
buffer_num = int(vim_eval("a:buffer_num"))
delete_buffer_cache(buffer_num)
----------------------- PythonCode ----------------------------------
endfunction

" Call the delete function when the BufDelete event happens.
augroup cyfolds_delete_buffer_cache
    autocmd!
    autocmd BufDelete *.py,*.pyx,*.pxd call DeleteBufferCache(expand('<abuf>'))
augroup END


" ==============================================================================
" ==== Turn off fold updating in insert mode, and update after TextChanged.  ===
" ==============================================================================

augroup cyfolds_unset_folding_in_insert_mode
    autocmd!
    "autocmd InsertEnter *.py,*.pyx,*.pxd setlocal foldmethod=marker " Bad: opens all folds.
    autocmd InsertEnter *.py,*.pyx,*.pxd if b:suppress_insert_mode_switching == 0 | 
                \ let b:insert_saved_foldmethod = &l:foldmethod | setlocal foldmethod=manual | endif
    autocmd InsertLeave *.py,*.pyx,*.pxd if b:suppress_insert_mode_switching == 0 |
                \ let &l:foldmethod = b:insert_saved_foldmethod  |
                \ if g:cyfolds_fix_syntax_highlighting_on_update | call FixSyntaxHighlight() | endif |
                \ endif
augroup END


" ==============================================================================
" ==== Define function to force a foldupdate.  =================================
" ==============================================================================

function! SetManual(timer)
    set foldmethod=manual
    "let timer=timer_start(s:timer_wait, { timer -> execute("let &l:foldmethod = b:update_saved_foldmethod") })
    "let timer=timer_start(s:timer_wait, { timer -> execute("set foldmethod=manual") })
endfunction

function! DelayManualMethod() abort
    let timer = timer_start(s:timer_wait, 'SetManual')
endfunction

function! FixSyntaxHighlight()
    " Reset syntax highlighting from the start of the file.
    if g:cyfolds_fix_syntax_highlighting_on_update && exists("g:syntax_on")
        syntax sync fromstart
    endif
endfunction


function! CyfoldsForceFoldUpdate()
    " Force a fold update.  Unlike zx and zX this does not change the
    " open/closed state of any of the folds.  Can be mapped to a key like 'x,'
    setlocal foldenable
    let b:update_saved_foldmethod = &l:foldmethod

    setlocal foldmethod=manual
    if b:update_saved_foldmethod != 'manual' " All methods except manual update folds.
        let &l:foldmethod = b:update_saved_foldmethod
    else
        setlocal foldmethod=expr
        " I had restore to manual mode with a delayed timer command in order
        " for the change to expr method above to register with vim and invoke
        " its side-effect of updating all the folds.  Just setting to manual
        " here does not work.
        "doautocmd <nomodeline> cyfolds_set_manual_method User
        let timer = timer_start(s:timer_wait, 'SetManual')
    endif
    if g:cyfolds_fix_syntax_highlighting_on_update
        call FixSyntaxHighlight()
    endif
endfunction


" ==============================================================================
" ==== Define some general functions. ==========================================
" ==============================================================================

function! CyfoldsToggleManualFolds()
    " Toggle folding method between current one and manual.  Useful when
    " editing a lot and the slight delay on leaving insert mode becomes annoying.
    if &l:foldmethod != 'manual'
        setlocal foldmethod=manual
    else
        setlocal foldmethod=expr
        "call CyfoldsForceFoldUpdate() " Not needed; above line does it.
    endif
    echom "foldmethod=" . &l:foldmethod
endfunction


function! CyfoldsSetFoldKeywords(keyword_str)
   " Dynamically assign the folding keywords to those on the string `keyword_str`.
   let g:cyfolds_fold_keywords = a:keyword_str
python3 << ----------------------- PythonCode ----------------------------------
cyfolds_fold_keywords = vim_eval("a:keyword_str")
setup_regex_pattern(cyfolds_fold_keywords)
----------------------- PythonCode ----------------------------------
   call CyfoldsForceFoldUpdate()
endfunction


" ==============================================================================
" ==== Modify foldline to look good with folded Python. ========================
" ==============================================================================

function! IsEmpty(line)
    return line =~ '^\s*$'
endfunction

function! CyfoldsFoldText()
    let num_lines = v:foldend - v:foldstart + 1
    let foldstart = v:foldstart
    let line_indent = indent(foldstart)

    if foldstart > 0
        let line_indent = max([line_indent, indent(foldstart-1)])
    endif

    " What if you use foldstart itself?, always match first line!!!  Mostly
    " works, but blank lines after docstring cause problems, need to look
    " forward another in that case...

    " TODO: Could this look back a line or two if the prev line is empty,
    " without being too slow?  Docstring whitespace at cutoff point causes
    " ugly indents.  How about detect funs and classes w/o docstring
    " and add indent?
    "
    "let line_with_indent = v:foldstart - 1
    "while IsEmpty(line_with_indent) && line_with_indent >= 0
    "   line_with_indent -= 1
    "endwhile
    "let line_indent = indent(line_with_indent)

    "let line = getline(v:foldstart)
    "let sub = substitute(line, '/\*\|\*/\|{{{\d\=', '', 'g')
    "
    return repeat(' ', line_indent) . '+---- ' . num_lines . ' lines ' . v:folddashes
endfunction


" Redefine search, maybe open:
" https://stackoverflow.com/questions/54657330/how-to-override-redefine-vim-search-command
"
" something like :g/egg/foldopen
" https://stackoverflow.com/questions/18805584/how-to-open-all-the-folds-containing-a-search-pattern-at-the-same-time

let &cpo = s:cpo_save
unlet s:cpo_save

