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
                   \ . "| unlet! b:cyfolds_suppress_insert_mode_switching"
                   \ . " w:cyfolds_saved_foldmethod_update"
                   \ . " w:cyfolds_saved_foldmethod_insert"
                   \ . " b:cyfolds_foldlevel_array"


" ==============================================================================
" ==== Initialization. =========================================================
" ==============================================================================

if has('win32') || has ('win64')
    let s:vimhome = $VIM."/vimfiles"
else
    let s:vimhome = $HOME."/.vim"
endif

if !exists('g:cyfolds_fold_keywords')
    let g:cyfolds_fold_keywords = 'class,def,async def'
endif

if !exists('g:cyfolds_start_in_manual_method')
    let g:cyfolds_start_in_manual_method = 1
endif

if !exists('g:cyfolds_lines_of_module_docstrings')
    let g:cyfolds_lines_of_module_docstrings = -1
endif

if !exists('g:cyfolds_lines_of_fun_and_class_docstrings')
    let g:cyfolds_lines_of_fun_and_class_docstrings = -1
endif

if !exists('g:cyfolds_fix_syntax_highlighting_on_update')
    let g:cyfolds_fix_syntax_highlighting_on_update = 0
endif

if !exists('g:cyfolds_no_initial_fold_calc')
    let g:cyfolds_no_initial_fold_calc = 0
endif

if !exists('g:cyfolds_update_all_windows_for_buffer')
    let g:cyfolds_update_all_windows_for_buffer = 0
    " TODO: document that global config values can't be updated on fly!!!
    " Using `get` might work (see links).  Also, doc the var in general and its default value.
    " https://www.reddit.com/r/vim/comments/7bcado/setting_default_values_for_plugins_global/
    " https://stackoverflow.com/questions/24660550/how-can-i-set-a-global-variable-from-a-script-command-line
    " https://stackoverflow.com/questions/15309218/vim-where-to-put-default-values-for-plugin-variables
    let g:cyfolds_update_all_windows_for_buffer = 1
endif

function! s:CyfoldsBufWinEnterInit()
    " Initialize upon entering a buffer.

    setlocal foldexpr=GetPythonFoldViaCython(v:lnum)
    setlocal foldtext=CyfoldsFoldtext()

    " Map the keys zuz and z, to their commands.
    nnoremap <buffer> <silent> zuz :call CyfoldsForceFoldUpdate()<CR>
    nnoremap <buffer> <silent> z, :call CyfoldsToggleManualFolds()<CR>

    " Initialize variables.
    let b:cyfolds_suppress_insert_mode_switching = 0
    let b:cyfolds_keyword_change = 0

    let b:cyfolds_saved_changedtick = -1
    let b:cyfolds_saved_shiftwidth = &shiftwidth
    let b:cyfolds_saved_lines_of_module_docstrings = g:cyfolds_lines_of_module_docstrings
    let b:cyfolds_saved_lines_of_fun_and_class_docstrings = g:cyfolds_lines_of_fun_and_class_docstrings

    " Force an initial fold update unless the user opted out of it.
    if g:cyfolds_no_initial_fold_calc != 1
        if g:cyfolds_start_in_manual_method != 1
            setlocal foldmethod=expr " Slightly faster if we don't need to change back.
        else
            call s:BufferWindowsSetFoldmethod('expr', '', 0)
        endif
    else
        setlocal foldmethod=manual
    endif

    " Switch to manual mode if that was the chosen foldmethod.
    if g:cyfolds_start_in_manual_method == 1 && &foldmethod != 'manual'
        setlocal foldmethod=manual
        "call s:BufferWindowsSetFoldmethod('manual', '', 0)
        "let timer = timer_start(s:timer_wait, 'SetFoldmethodManual')
    endif
endfunction

augroup cyfolds_buf_new_init
    " Using BufWinEnter, but BufEnter event seems to work, too; not sure which
    " is best or if it matters.  BufNew and BufAdd don't work.
    "    |BufWinEnter|   after a buffer is displayed (first time) in a window
    "    |BufEnter|      after entering (first time) a buffer
    " The |WinEnter| event fires each time you enter a window.
    " https://vim.fandom.com/wiki/Detect_window_creation_with_WinEnter
    autocmd!
    "autocmd BufEnter *.py,*.pyx,*.pxd :call CyfoldsBufWinEnterInit()
    autocmd BufWinEnter *.py,*.pyx,*.pxd :call s:CyfoldsBufWinEnterInit()
augroup END


python3 << ----------------------- PythonCode ----------------------------------
"""
    Python initialization code.  Import the functions `call_get_foldlevels`,
    and `setup_regex_pattern`.  Initialize the regex patterns (of keywords to
    fold under).
"""
import sys
from os.path import normpath, join
import vim

import cyfolds
# These vars are set in cyfolds.py to try to accomodate slowness issues when in Neovim.
# https://github.com/neovim/neovim/issues/7063
vim_eval = cyfolds.vim_eval
#vim_command = cyfolds.vim_command # Defined but no currently used here.
#vim_current_buffer = cyfolds.vim_current_buffer # Defined but not currently used here.

# Put the .vim directory's python3 subdirectory on sys.path so the plugin can be imported.
vimhome = vim_eval("s:vimhome")
cyfolds_fold_keywords = vim_eval("cyfolds_fold_keywords")
python_root_dir = normpath(join(vimhome, 'python3'))
sys.path.insert(0, python_root_dir)

from cyfolds import setup_regex_pattern, call_get_foldlevels
setup_regex_pattern(cyfolds_fold_keywords)
----------------------- PythonCode ----------------------------------


" ==============================================================================
" ==== Define the function GetPythonFoldViaCython to be set as foldexpr.========
" ==============================================================================

function! s:CyfoldsChangeDetector()
    " Detect changes that require recalculating the foldlevels.
    if b:cyfolds_saved_changedtick != b:changedtick
        " Could also use undotree().seq_cur instead of b:changedtick.
        let b:cyfolds_saved_changedtick = b:changedtick
        return 1
    elseif b:cyfolds_saved_shiftwidth != &shiftwidth
        let b:cyfolds_saved_shiftwidth = &shiftwidth
        return 1
    elseif b:cyfolds_saved_lines_of_module_docstrings != g:cyfolds_lines_of_module_docstrings
        let b:cyfolds_saved_lines_of_module_docstrings = g:cyfolds_lines_of_module_docstrings
        return 1
    elseif b:cyfolds_saved_lines_of_fun_and_class_docstrings != g:cyfolds_lines_of_fun_and_class_docstrings
        let b:cyfolds_saved_lines_of_fun_and_class_docstrings = g:cyfolds_lines_of_fun_and_class_docstrings
        return 1
    elseif b:cyfolds_keyword_change != 0
        let b:cyfolds_keyword_change = 0
        return 1
    endif
    return 0
endfunction

function! GetPythonFoldViaCython(lnum)
    " This function is evaluated for each line and returns the folding level.
    " It is set as the foldexpr.
    " https://candidtim.github.io/vim/2017/08/11/write-vim-plugin-in-python.html
    " How to return Python values back to vim: https://stackoverflow.com/questions/17656320/
    if a:lnum == 1 && s:CyfoldsChangeDetector()
        python3 call_get_foldlevels()
    endif
    " echom a:lnum
    return b:cyfolds_foldlevel_array[a:lnum-1]
endfunction


" ==============================================================================
" ==== Turn off fold updating in insert mode, and update after TextChanged.  ===
" ==============================================================================

" TODO: Document the new behavior.  If g:cyfolds_update_all_windows_for_buffer
" is set to 1 then on exiting insert mode all windows for the modified buffer
" which have `expr` set as the foldmethod have their folds updated.

augroup cyfolds_unset_folding_in_insert_mode
    " Note you can stay in insert mode when changing windows or buffer (like with mouse).
    " See https://vim.fandom.com/wiki/Keep_folds_closed_while_inserting_text
    autocmd!

    autocmd InsertEnter *.py,*.pyx,*.pxd 
                \ if b:cyfolds_suppress_insert_mode_switching == 0 | 
                \     call s:BufferWindowsSetFoldmethod('manual', 'cyfolds_saved_foldmethod_insert',
                \                                       g:cyfolds_update_all_windows_for_buffer) |
                \ endif

    " TODO: Maybe set InsertLeave for all filetypes later, not just Python, so you can move to any buffer with
    " mouse click during insert and still restore on exit.
    " TODO: Does syntax highlighting need to be per-buffer too?
    autocmd InsertLeave *.py,*.pyx,*.pxd
                \ if b:cyfolds_suppress_insert_mode_switching == 0 |
                \     call s:BufferWindowsRestoreFoldmethod('cyfolds_saved_foldmethod_insert',
                \                                           g:cyfolds_update_all_windows_for_buffer) |
                \     if g:cyfolds_fix_syntax_highlighting_on_update |
                \         call s:FixSyntaxHighlight() |
                \     endif |
                \ endif
augroup END


" ==============================================================================
" ==== Utility functions used in other routines. ===============================
" ==============================================================================

function! s:FixSyntaxHighlight()
    " Reset syntax highlighting from the start of the file.
    if g:cyfolds_fix_syntax_highlighting_on_update && exists('g:syntax_on')
        syntax sync fromstart
    endif
endfunction

function! s:WinDo(command)
    " Just like windo, but restore the current window when done.
    " See https://vim.fandom.com/wiki/Windo_and_restore_current_window
    let currwin=winnr()
    execute 'windo ' . a:command
    execute currwin . 'wincmd w'
endfunction
command! -nargs=+ -complete=command CyfoldsWindo call s:WinDo(<q-args>)
command! -nargs=+ -complete=command CyfoldsWindofast noautocmd call s:WinDo(<q-args>)

function! s:CurrWinDo(command)
    " Run the command with windo but only in the current window.  (Used for
    " the side-effect of forcing folding on changing foldmethod.)
    let currwin=winnr()
    execute 'windo if winnr() == currwin | ' . a:command . ' | endif'
    execute currwin . 'wincmd w'
endfunction
command! -nargs=+ -complete=command CyfoldsCurrWindo call s:CurrWinDo(<q-args>)
command! -nargs=+ -complete=command CyfoldsCurrWindofast noautocmd call s:CurrWinDo(<q-args>)

"function! s:BufDo(command)
"    " Just like bufdo, but restore the current buffer when done.
"    " See https://vim.fandom.com/wiki/Windo_and_restore_current_window
"    let currBuff=bufnr("%")
"    execute 'bufdo ' . a:command
"    execute 'buffer ' . currBuff
"endfunction
"command! -nargs=+ -complete=command CyfoldsBufdo call s:BufDo(<q-args>)
"command! -nargs=+ -complete=command CyfoldsBufdofast noautocmd call s:BufDo(<q-args>)

" ==============================================================================
" ==== Define the function to force fold updates in all windows for buffer.  ===
" ==============================================================================

function s:WindowSetFoldmethod(foldmethod, save_var)
    " Set the window-local foldmethod to the given one.  If `save_var` is a
    " non-empty sting then the old setting is saved with the window-scope
    " variable of that name (don't include the `w:` in the string).
    if a:save_var != ''
        let save_varname = 'w:' . a:save_var
        execute 'let ' . save_varname . ' = &l:foldmethod'
    endif
    execute "setlocal foldmethod=" . a:foldmethod
endfunction

function s:WindowRestoreFoldmethod(restore_var)
    " Restore the foldmethod to the value stored in the window-scope variable
    " named `restore_var` (don't include the `w:` in the string).
    let restore_varname = 'w:' . a:restore_var
    execute "let restore_value = " . restore_varname
    if !exists(restore_varname)
       return
    endif
    execute 'setlocal foldmethod=' . restore_value
    execute 'unlet ' . restore_varname
endfunction

function! s:BufferWindowsSetFoldmethod(foldmethod, save_var, all_wins_for_buf)
    " Set the foldmethod to `foldmethod` in all windows for the current
    " buffer.
    "
    " If `save_var is a non-empty string then the previous setting is
    " also saved in the window-scope variable of that name.
    "
    " If `all_wins_for_buf` is 0 then only the current window is updated (this
    " differs from setting the foldmethod directly because it also causes the
    " side-effect of fold-evaluation on setting foldmethod=eval).
    let s:curbuf = bufnr('%')
    let cmd_str =  "if bufnr('%') is s:curbuf | "
                \.     "call s:WindowSetFoldmethod('" . a:foldmethod . "', '" . a:save_var . "') | "
                \. "endif"

    if a:all_wins_for_buf
        silent! execute "CyfoldsWindofast " . cmd_str
    else
        silent! execute "CyfoldsCurrWindofast " . cmd_str
    endif
endfunction

function! s:BufferWindowsRestoreFoldmethod(restore_var, all_wins_for_buf)
    " Restore the foldmethod to the saved value in all windows for the current buffer
    " using the value saved in the window-scope variable named `restore_var`.
    let s:curbuf = bufnr('%')
    let cmd_str =  "if bufnr('%') is s:curbuf | "
                \.     "call s:WindowRestoreFoldmethod('" . a:restore_var . "') | "
                \. "endif"

    if a:all_wins_for_buf
        silent! execute "CyfoldsWindofast " . cmd_str
    else
        silent! execute "CyfoldsCurrWindofast " . cmd_str
    endif
endfunction

function! CyfoldsPlainForceFoldUpdate()
    " Force a fold update and nothing else.  Unlike zx and zX this does not
    " change the open/closed state of any of the folds.
    " 
    " Note that when `zx` recalculates the folds it ONLY applies to the current
    " window, and it only works with `expr` foldmethod (since the function set there
    " is how folding is implemented/calculated).  The `zX` command is the same but
    " doesn't also do a `zv` to open cursor's fold.

    " Note you don't need to set to manual first, even if already in expr mode.
    "call s:BufferWindowsSetFoldmethod('manual', 'cyfolds_saved_foldmethod_update', g:cyfolds_update_all_windows_for_buffer)
    call s:BufferWindowsSetFoldmethod('expr', 'cyfolds_saved_foldmethod_update', g:cyfolds_update_all_windows_for_buffer)
    "call s:BufferWindowsSetFoldmethod('expr', '', g:cyfolds_update_all_windows_for_buffer)
    call s:BufferWindowsRestoreFoldmethod('cyfolds_saved_foldmethod_update', g:cyfolds_update_all_windows_for_buffer)
endfunction

function! CyfoldsForceFoldUpdate()
    " Force a fold update, but also set foldenable and do syntax updating if
    " the user selected that option.
    setlocal foldenable
    call CyfoldsPlainForceFoldUpdate()
    if g:cyfolds_fix_syntax_highlighting_on_update
        call s:FixSyntaxHighlight()
    endif
endfunction


" ==============================================================================
" ==== Define some general Cyfolds functions. ==================================
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


function! CyfoldsUpdateFoldKeywords()
   " Dynamically assign the folding keywords to those on the string `keyword_str`.
python3 << ----------------------- PythonCode ----------------------------------
cyfolds_fold_keywords = vim_eval("g:cyfolds_fold_keywords")
setup_regex_pattern(cyfolds_fold_keywords)
----------------------- PythonCode ----------------------------------
    let b:cyfolds_keyword_change = 1
    call CyfoldsForceFoldUpdate()
endfunction


" ==============================================================================
" ==== Modify foldline to look good with folded Python. ========================
" ==============================================================================

function! s:IsEmpty(line)
    " Currently unused.
    return line =~ '^\s*$'
endfunction

function! CyfoldsFoldtext()
    let num_lines = v:foldend - v:foldstart + 1
    let foldstart = v:foldstart
    let line_indent = indent(foldstart)

    if foldstart > 0
        let line_indent = max([line_indent, indent(foldstart-1)])
    endif

    return repeat(' ', line_indent) . '+---- ' . num_lines . ' lines ' . v:folddashes
endfunction

" ==============================================================================
" ==== Older function to force a foldupdate only in current window (unused).====
" ==============================================================================

let s:timer_wait = 500 " Timer wait in milliseconds, time before switch to manual.

function! SetFoldmethodManual(timer)
    " This is called from a timer to set foldmethod to manual after it has been set to expr.
    " If the foldmethod is immediately set to manual without the delay the side-effect of
    " recalculating folds (due to setting to expr) does not occur.
    setlocal foldmethod=manual
endfunction

function! CyfoldsForceCurrentWindowOnlyFoldUpdate()
    " Force a fold update.  Unlike zx and zX this does not change the
    " open/closed state of any of the folds.
    "
    " Instead of using windo to set the foldmethods and get the fold-recalculate
    " side-effect this method uses a small timer delay on resetting to manual
    " foldmethod.
    setlocal foldenable
    let w:cyfolds_saved_foldmethod_update = &l:foldmethod

    setlocal foldmethod=manual
    if w:cyfolds_saved_foldmethod_update != 'manual' " All methods except manual update folds.
        let &l:foldmethod = w:cyfolds_saved_foldmethod_update
    else
        setlocal foldmethod=expr
        " Restore to manual mode with a delayed timer command in order for the change
        " to expr method above to register with vim and invoke its side-effect of
        " updating all the folds.  Just setting to manual here does not work.
        let timer = timer_start(s:timer_wait, 'SetFoldmethodManual')
    endif
    if g:cyfolds_fix_syntax_highlighting_on_update
        call FixSyntaxHighlight()
    endif
endfunction


let &cpo = s:cpo_save
unlet s:cpo_save

