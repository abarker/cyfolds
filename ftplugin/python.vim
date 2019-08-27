" alb: Files in the ftplugin only are loaded depending on filetype,
" based on the filename.  This is currently all my code.

" =========================================================================
" This works really well modulo a few remaining bugs in nested classes and
" functions.  BUT it is super-slow.  Using FastFold might help some to reduce
" the updating that is done, but updating is still slow.  Approaches to 
" speed up:
"
" 1) Memoize in a vimscript dict.  Seems to update from 1 to numlines, so
" when going up to find fundef you can usually just use the same value as
" the line above, which has already been computed (?).  Example vimscript
" memoization code:
" https://www.projectiwear.org/home/svn/iwear/src/trunk/vim/_vim/bundle/vim-ingo-library/autoload/ingo/collections/memoized.vim
"
" 2) See ':help fold-expr'.  Here is the relevant text:

"   Note: Since the expression has to be evaluated for every line, this fold
"   method can be very slow!
"
"   Try to avoid the "=", "a" and "s" return values, since Vim often has to
"   search backwards for a line for which the fold level is defined.  This can
"   be slow.
"
"   |foldlevel()| can be useful to compute a fold level relative to a previous
"   fold level.  But note that foldlevel() may return -1 if the level is not
"   known yet.  And it returns the level at the start of the line, while a
"   fold might end in that line.
"
" 3) Final option is to use Python-wrapped C code (Cython?) to speed up the
"    function.  Or, since you can import code, maybe numba?
"
"    Maybe just read the whole buffer when evaluated for line 1, trashing any
"    cache, and recompute for whole file and caching the new results.  Then
"    later calls just return cached value.
"
" Special properties of my folding definition to exploit:
" 
" 1) Indent levels are always the same as the previous indent level EXCEPT
"    when the previous non-empty line starts with fun/class OR when the previous
"    non-empty line ends with the closing triple-quote of a docstring.
"
"    This means sequential eval can be fairly fast, and the -1 value never
"    needs to be returned (which might cause problem when empty lines are
"    unevalated.  For empty lines, just return foldlevel(PreviousNonempty(current)),
"    maybe looking ahead one or two for def/class to keep some space between
"    folds.
"
" =========================================================================

" Notes on vimscript:
"
" Variables: The prefixes like g:, s:, a:, are scope.
"
" - g: is global
" - a: is function argument list (numeric for varargs or keyword)
" - s: is local to the current script file
" - b: local to buffer
" - l: local to function
" Etc. https://www.gilesorr.com/blog/vim-variable-scope.html
"
" Comparison:
"
" Use the case-insensitive comparison ==# in preference to ==
"
" Vim treats 0 and 1 as truthy, and coerces strings to it.  Logical negation
" is ! and it uses && and || as connectives.

"=========================================================================
"=== apply formatter to Python docstring =================================
"=========================================================================
" TODO: Test that the immediately-preceding "def" or "class" statement is
" dedented one dedent from the current indent.  See commented out code above
" for the basic parts and pieces... Otherwise works between two docstrings.
"
" Consider: you could just send the whole file to Python along with the line
" number, mod the relevant part, and replace the whole thing.  Or send whole
" thing from previous dedented "def" or "class" up to following dedent for
" efficiency.  Might also work for folding experiment above... find that "def"
" line and then go back down to first indented line starting with """!

function! StartsWithTripleQuote(lnum) " alb
   " Fake boolean for whether line starts with triple quote.
   "if getline(a:lnum) =~? '\v^\s""".*\s'
   if getline(a:lnum) =~? '\v^\s*""".*\s'
      return 1
   else
      return 0
   endif
endfunction

function! EndsWithTripleQuote(lnum)
   " Fake boolean for whether line ends with triple quote.
   if getline(a:lnum) =~? '\v^.*"""\s*$'
      return 1
   else
      return 0
   endif
endfunction

function! ClosingTripleQuoteLineNum(lnum)
   " Get the line number of the closing (next first-on-line) triple quote after a given line.
   let numlines = line('$') " Store the total number of lines in the file.
   let current = a:lnum
   let arg_line_indent = IndentLevel(a:lnum)

   while current <= numlines
      if EndsWithTripleQuote(current) == "1"
         return current
      endif

      let current += 1
   endwhile

   return -2
endfunction

function! OpeningTripleQuoteLineNum(lnum)
   " Get the line number of the opening (prev first-on-line) triple quote after a given line.
   let current = a:lnum

   while current > 0
      if StartsWithTripleQuote(current) == "1"
         return current
      endif

      let current -= 1
   endwhile

   return -2
endfunction

function! DocstringFormat()
   " Get the number of the line that closes the docstring.
   let starting = OpeningTripleQuoteLineNum(line("."))
   let ending = ClosingTripleQuoteLineNum(line("."))
   if starting == "-2" || ending == "-2"
      return
   endif
   execute starting . "," . ending . "!dsfmt"
endfunction

" Define new vim command for the function.
command! Dsfmt call DocstringFormat() " The ! overwrites or problem with multiple..
"command Dsfmt echo StartsWithTripleQuote(line("."))

"=========================================================================
" ================= Test custom foldexpr =================================
"=========================================================================
" http://learnvimscriptthehardway.stevelosh.com/chapters/49.html
" https://vi.stackexchange.com/questions/2176/how-to-write-a-fold-expr

" TODO: function set_cropped_metadata still has some problems with nested
" funs and classes.................
setlocal foldmethod=expr
setlocal foldexpr=GetPythonFoldPython(v:lnum)

function! IndentLevel(lnum)
   " Return the indent level of line at number lnum.
   return indent(a:lnum) / &shiftwidth " & converts to number (??)
endfunction

function! NextNonEmptyLine(lnum)
   " Get the number of the next non-empty line after a given line.
   let numlines = line('$') " Store the total number of lines in the file.
   let current = a:lnum + 1

   while current <= numlines
      if getline(current) =~? '\v\s'
         return current
      endif

      let current += 1
   endwhile

   return -2
endfunction

function! PrevNonEmptyLine(lnum)
   " Get the number of the prev non-empty line after a given line.
   let numlines = line('$') " Store the total number of lines in the file.
   let current = a:lnum + 1

   while current > 0
      if getline(current) =~? '\v\s'
         return current
      endif

      let current -= 1
   endwhile

   return -2
endfunction

function! StartsWithClassOrDef(lnum) " alb
   " Fake boolean for whether line starts with triple quote.
   "if getline(a:lnum) =~? '\v^\s""".*\s'
   "TODO BUG, maybe unavoidable: this matches inside strings, too!!  May need
   "to restrict to zero-level funs and classes only (and assume sane strings).
   if getline(a:lnum) =~? '\v^\s*def.*\s' || getline(a:lnum) =~? '\v^\s*class.*\s' || getline(a:lnum) =~? '\v^\s*async def.*\s'
      return 1
   else
      return 0
   endif
endfunction

function! PrevFundefLineNum(lnum)
   let numlines = line('$') " Store the total number of lines in the file.
   let current = a:lnum
   let initial_indent = IndentLevel(a:lnum)
   let min_indent_level = initial_indent

   " Go up, looking for class or function definition.
   while current > 0
      if LineIsEmpty(current)
         let current -= 1
         continue
      endif
      let current_indent_level = IndentLevel(current)
      if current_indent_level < min_indent_level && StartsWithClassOrDef(current) == "1"
         return current " Found the definition.
      elseif current_indent_level == 0
         return -2 " Nonindented line cannot be inside a function.
      endif
      if current_indent_level < min_indent_level
         let min_indent_level = current_indent_level
      endif
      let current -= 1
   endwhile

   return -2
endfunction

function! OpeningDocstringLineNumAfterPrevFundef(lnum)
   let numlines = line('$') " Store the total number of lines in the file.
   let current = a:lnum

   " Go up, looking for class or function definition.
   let def_or_class_line_num = PrevFundefLineNum(current)
   let def_or_class_line_indent = IndentLevel(def_or_class_line_num)

   if def_or_class_line_num == "-2"
      return -2
   endif

   " Found the def or class line, now go forward back down the file.
   let current = def_or_class_line_num + 1
   while current <= numlines
      let current_line_indent = IndentLevel(current)
      if current_line_indent <= def_or_class_line_indent " Same level or dedent from fundef line.
         if LineIsEmpty(current)
            let current += 1
            continue
         endif
         return -2 " This assumes docstrings use sane formatting, not into the indent region.
      elseif current_line_indent > def_or_class_line_indent + 1
         let current += 1 " Skip lines between def/class and opening triple quote (sane formatting assumed).
      elseif current_line_indent == def_or_class_line_indent + 1 " Got ending. (This could be an else stmt.)
         return current
      endif
   endwhile

   return -2
endfunction

function! LineIsEmpty(lnum)
   if getline(a:lnum) =~? '\v^\s*$'
      return 1
   else
      return 0
endfunction

function! Echom(lnum)
   echom a:lnum '.............................................'
endfunction

function! GetPythonFold(lnum)
   " This fun is evaluated for each line, tells folding level.
   " Regex below matches: "beginning of line, any number of whitespace, end of line"
   "
   " Use
   "     echom <var> <var> ...
   " to debug, shows last one.
   "
   " Note this assumes sane formatting for docstrings, comments, and function
   " arguments not to intrude into the usual indent whitespace zone.
   let current = a:lnum
   echom current
   if LineIsEmpty(current) == "1"
      " DEBUG, optimization test... may want to forward one or two for startswith fun/class.
      "if StartsWithClassOrDef(current + 1) == "1":
      "   return IndentLevel(current + 1)
      return foldlevel(current - 1)
      return '-1' " Foldlevel undefined; use min of lines above and below.
   endif
   let this_indent = IndentLevel(current)

   " DEBUG optimize test, below works find BUT not significantly faster!!
   if StartsWithClassOrDef(current - 1) != 1 && EndsWithTripleQuote(current - p) != 1
      return foldlevel(current - 1) " DEBUG, test... may want to forward one or two for startswith fun/class.
   endif

   " todo since we get here, no need to get again in OpeningDocstringLineNumAfterPrevFundef
   let def_or_class_line_num = PrevFundefLineNum(current)
   let def_or_class_line_indent = IndentLevel(def_or_class_line_num)

   let docstring_open_lnum = OpeningDocstringLineNumAfterPrevFundef(current)
   if docstring_open_lnum != "-2"
      let docstring_open_indent_level = IndentLevel(docstring_open_lnum)
      let docstring_close_lnum = ClosingTripleQuoteLineNum(docstring_open_lnum)
      if docstring_close_lnum != "-2"
         let first_nonempty_after_close = NextNonEmptyLine(docstring_close_lnum)
         let first_nonempty_indent_level = IndentLevel(first_nonempty_after_close)
         if first_nonempty_indent_level == docstring_open_indent_level
            if current >= def_or_class_line_num && current <= docstring_close_lnum
               " Keep stuff after def/class down to closing docstring same as def/class.
               return def_or_class_line_indent " Level with fun def.
            elseif current == first_nonempty_after_close
               " Starting line for indent.
               return ">" . first_nonempty_indent_level " Fold at this level starts here.
            else
               " Indented line after starting line.
               return first_nonempty_indent_level
            endif
         endif
      endif
   endif

   return 0
   return this_indent " Just set to current indent level, but does if, for, etc. too.
   return def_or_class_line_indent " Closes whole thing, always.
endfunction

" ==============================================================================
" ==== Python version, set up call to the Python script ========================
" ==============================================================================

function! GetPythonFoldPython(lnum)
" This fun is evaluated for each line, tells folding level.
" https://candidtim.github.io/vim/2017/08/11/write-vim-plugin-in-python.html
" https://stackoverflow.com/questions/17656320/using-python-in-vimscript-how-to-export-a-value-from-a-python-script-back-to-vi

   if has('win32') || has ('win64')
      let vimhome = $VIM."/vimfiles"
   else
      let vimhome = $HOME."/.vim"
   endif

   let g:pyfoldlevel = '' " Global var for return value.
   let g:foldnestmax = 2 " Global var for return value, ignore actual (can't read it!)

python3 << ---------------------------PythonCode----------------------------------

init_done = False
if not init_done:
   #init_done = True
   import sys
   from os.path import normpath, join
   import vim
   vimhome = vim.eval("vimhome")
   python_root_dir = normpath(join(vimhome, 'python3'))
   sys.path.insert(0, python_root_dir)
#from calc_folds import foldlevel
from  cyfolds import foldlevel

lnum = vim.eval("a:lnum")
shiftwidth = vim.eval("&shiftwidth")
foldnestmax = vim.eval("g:foldnestmax")
flevel = foldlevel(lnum, foldnestmax, shiftwidth)
vim.command("let g:pyfoldlevel = {}".format(flevel))

---------------------------PythonCode----------------------------------

   return g:pyfoldlevel

endfunction

" ==============================================================================
" ==== unset folding in insert mode ============================================
" ==============================================================================
" https://github.com/ycm-core/YouCompleteMe/issues/1395

"augroup unset_folding_in_insert_mode
"    autocmd!
"    autocmd InsertEnter *.py setlocal foldmethod=marker
"    autocmd InsertLeave *.py setlocal foldmethod=expr
"augroup END

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

" ==============================================================================
" ==== set colors ==============================================================
" ==============================================================================

" TODO: Works here, but not from syntax file......
"highlight Folded     guifg=Grey30                       gui=NONE cterm=NONE
highlight Folded guifg=Grey30
highlight FoldColumn guifg=Grey30

