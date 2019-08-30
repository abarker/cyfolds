#cython: language_level=3
"""

Cyfolds
=======

Program to set vim folding levels for Python code.  Made to be syntax-based and
fast.  Only classes and functions are folded, and docstrings are left unfolded
on the same level as the definition line.

Notes:
------

* vim.current.buffer is the current buffer, list-like.  It is modifiable.

* Lines number from zero in Python buffer object, but vim uses 1-based
  numbering.

* The vim Python API docs (same as ':help python'):
    https://vimhelp.org/if_pyth.txt.html

Theory
------

The code processes the text buffer in one pass through the file, line by line,
character by character, skipping characters when it can (such as by ignoring
comment text).

On the first part of a pass for line the program sets various properties of the
line, such as the nesting level, whether it is currently quoted, etc.  In the
second part this data feeds into what is essentially a state machine that
figures out what foldlevel to set for the line.

The state machine that the program runs over lines looks like this,
going down from the top:

            begin_fun_or_class_def -------------------->|
                      |                                 |
                      |<-----------------------inside_fun_or_class_def
                      |
                      |
     |<---- just_after_fun_or_class_def --------------->|
     |                |                                 |
     |                |<---------------------- inside_docstring
     |                |
     |                |
     |      just_after_fun_docstring
     |                |
     |                |
     ----> [increase line's foldlevel]

The two "inside" states can also loop back to themselves: they eat function
parameters spread over multiple lines and the text inside multiline docstrings.
The actual ordering of the states in the file is in reverse, so that
states do not trigger next states until the next loop (line) through.

Foldlevel values are calculated for all the lines during the pass through the
buffer and are saved in `foldlevel_cache`.  When `foldlines` is called a hash
is first computed over all the lines in the buffer.  This hash is compared
against a saved hash value for the previous buffer.  If they are the same then
the cached foldlevel value for the line is returned.  Otherwise another pass is
made through the file, recomputing the foldlevels.  This assumes that the time
to compute the hash is less than the time to recompute the data up to the line
needed.  Empirically, this does significantly speed up the processing,
especially on startup.

Possible enhancements
---------------------

* If you set the foldlevel bump to a really high number for things like for,
  while, and if then you should be able to syntactically define the initial state
  of the folds, open or closed, by setting foldlevel.  See :help foldlevelstart.

* Add options to also fold for, while, if, with, and try.  Have a function that
  is passed the arguments for what to fold which then sets and compiles a global
  regex to use.  They mostly work now, but not all cases (at least not tested).
  Also, cdef for Cython code::

     let g:cyfolds_keywords_closed_by_default = ['def', 'async def', 'class', 'cdef']
     let g"cyfolds_keywords_open_by_default = ['if', 'for', 'while']

* Find a faster way to tell if the buffer changed, i.e., if the cache is dirty.
  If you had the precise line numbers of all the changes you could speed up the
  updates by jumping ahead (keep enough state data) and start there.  Keep going
  forward past last change spot until the current foldlevel agrees with the
  previous one for lines not changed.

  You could just save a copy of the buffer.  Then go through and find the
  changed lines.  Or save a hash of each line if it's too much memory to save
  the whole thing.  Or maybe hash blocks of, say, 10 lines and take line
  numbers mod that number.  But is this maybe slower than just computing the
  folds over the whole file (which is pretty fast)?  You need to at least
  search or hash over the whole file to tell what changed.

* Maybe have an option to number indents by number of spaces.  Might be more
  line what some people expect, such as when a function definition is nested
  inside a for loop.

* Make sure line ends in semicolon at end of fundef, while, etc., just as an
  extra check that's easy to do.  Otherwise, don't do new fold.

"""

DEBUG: bint = False
TESTING: bint = False
USE_CACHING = True

try:
    import vim
except ImportError:
    TESTING = True

if TESTING:
    # These classes mock vim.buffer.current, for testing.
    class Current:
        buffer = []
    class vim:
        current = Current

from collections import namedtuple
from typing import List, Tuple, Set, Dict
import numpy as np

import cython as cy
from cpython cimport bool # Use Python bool.
from cython import bint # C int coerced to bool.
#from cpython cimport int # Use Python int.

prev_buffer_hash: Dict[cy.int, cy.int] = {} # Hashes indexed by buffer number.
foldlevel_cache: Dict[cy.int, List[cy.int]] = {} # Cache of all the computed foldlevel values.
recalcs: cy.int = 0 # Global counting the number of recalculations (for debugging).
foldfun_calls: cy.int = 0 # Global counting the number of calls to get_foldlevel (debugging)

def get_foldlevel(lnum: int, cur_buffer_num: int, cur_undo_sequence:int=None,
                  foldnestmax:int=20, shiftwidth:int=4, test_buffer=None):
    """Recalculate all the fold levels for line `lnum` and greater.  Note that this
    function is passed to vim, and expects `lnum` to be numbered from 1 rather than
    zero.  The `test_buffer` if for passing in a mock of the `vim.current.buffer`
    object in debugging and testing."""
    global recalcs, foldfun_calls # Debugging counts, persistent.

    foldnestmax = int(foldnestmax)
    shiftwidth = int(shiftwidth)
    lnum = int(lnum) - 1 # Compensate for different numbering convention.

    if not TESTING:
        buffer_lines = vim.current.buffer
    else:
        buffer_lines = test_buffer

    # Convert the buffer into an ordinary list of strings, for easier Cython.
    buffer_lines = tuple(i for i in buffer_lines)
    assert buffer_lines

    if USE_CACHING:
        if cur_undo_sequence is None:
            buffer_hash = hash(tuple(buffer_lines))
        else:
            buffer_hash = cur_undo_sequence
        dirty_cache = buffer_hash != prev_buffer_hash.get(cur_buffer_num, -1)
        prev_buffer_hash[cur_buffer_num] = buffer_hash
    else:
        dirty_cache = True
    #print(" prev_buffer_hash=", prev_buffer_hash[cur_buffer_num], " dirty=", dirty_cache, " calls=",
    #        foldfun_calls, " cur_buffer_num=", cur_buffer_num, type(cur_buffer_num), sep="")

    #print("updating folds========================================================begin", foldfun_calls)
    if dirty_cache:
        #print("updating folds, dirty........................................................", recalcs)
        # Get a new foldlevel_cache list and recalculate all the foldlevels.
        new_cache_list = [0] * len(buffer_lines)
        foldlevel_cache[cur_buffer_num] = new_cache_list
        calculate_foldlevels(new_cache_list, buffer_lines, shiftwidth)
        recalcs += 1
        #print("done with folds.......................................................done", recalcs)

    foldlevel = foldlevel_cache[cur_buffer_num][lnum]
    #foldlevel = min(foldlevel, foldnestmax)
    foldfun_calls += 1
    return foldlevel

def delete_buffer_cache(buffer_num: int):
    """Remove the saved cache information for the buffer with the given number.  This is meant to be
    called when the buffer is closed, to avoid wasting memory."""
    # This function is getting called twice for some reason, so check for the key before del.
    if buffer_num in prev_buffer_hash:
        del prev_buffer_hash[buffer_num]
    if buffer_num in foldlevel_cache:
        del foldlevel_cache[buffer_num]

cdef bint is_begin_fun_or_class_def(line: str, prev_nested: cy.int,
                                    in_string: cy.int, indent_spaces: cy.int,
                                    also_for:bint=False, also_while:bint=False):
        """Boolean for whether fun or class def begins on the line."""
        #also_for = True
        #also_while = True
        if prev_nested or in_string: return False
        if line[indent_spaces:indent_spaces+4] == "def ": return True
        # TODO: remember cython enabled here...
        if line[indent_spaces:indent_spaces+5] == "cdef ": return True
        if line[indent_spaces:indent_spaces+5] == "cpdef ": return True
        if line[indent_spaces:indent_spaces+6] == "class ": return True
        if line[indent_spaces:indent_spaces+10] == "async def ": return True
        if also_for and line[indent_spaces:indent_spaces+4] == "for ": return True
        if also_while and line[indent_spaces:indent_spaces+6] == "while ": return True
        return False

cdef void replace_preceding_minus_five_foldlevels(foldlevel_cache: List[cy.int],
                                             start_line_num: cy.int, foldlevel_value: cy.int):
    """Starting at index `start_line_num`, any immediately-preceding sequence of -5
    values is replaced by `foldlevel_value`."""
    if not foldlevel_cache:
        return
    lnum_loopback: cy.int = start_line_num
    while lnum_loopback >= 0 and foldlevel_cache[lnum_loopback] == -5:
        foldlevel_cache[lnum_loopback] = foldlevel_value
        lnum_loopback -= 1

cdef cy.int increase_foldlevel(foldlevel_stack: List[cy.int], fold_indent_spaces_stack:
                     List[cy.int], new_foldlevel: cy.int, new_fold_indent_spaces: cy.int):
    """The fun/class defs define the new fold levels, but they're deferred for possible
    docstrings.  Also, levels are saved so things which
    dedent can return to that level (like after nested fun defs)."""
    if DEBUG: print("   --> increasing foldlevel to {}".format(new_foldlevel))

    if new_foldlevel > foldlevel_stack[-1]:
        foldlevel_stack.append(new_foldlevel)
        fold_indent_spaces_stack.append(new_fold_indent_spaces)
    return new_foldlevel

cdef cy.int get_foldlevel_increment(curr_foldlevel: cy.int, indent_spaces: cy.int,
                                    shiftwidth: cy.int):
    """Return the increment in the shiftlevel.  Currently just returns 1 or maybe the
    shiftwidth, but later may take more parameters such as the recognized keyword."""
    increment: cy.int
    # Constant increment works, and always gives sequential increases regardless of indent.
    #increment = 1

    # With this method the foldlevel always equals the indent spaces divided by shiftwidth,
    # i.e., the number of indent levels.  But, it gives weird behavior on vim.  The
    # number of za commands to open a fold seems to be increased when the level jumps...
    # Same thing for zo.  May kill the idea of default open/closed by incrementing.
    # But using 100zo gives the behavior I expect on open and is still fast.
    increment = indent_spaces // shiftwidth - curr_foldlevel + 1
    assert increment >= 0
    return increment

cdef void calculate_foldlevels(foldlevel_cache: List[cy.int], buffer_lines: List[str],
                               shiftwidth: cy.int):
    """Do the actual calculations and return the foldlevel."""

    # States in the state machine.
    inside_fun_or_class_def: bint = False
    just_after_fun_or_class_def: bint = False
    inside_docstring: bint = False
    just_after_fun_docstring: bint = False

    # Stacks holding the current foldlevels and their indents, highest on top.
    foldlevel_stack: List[cy.int] = [0]
    fold_indent_spaces_stack: List[cy.int] = [0]

    # New foldlevels and copies saved to avoid overwrites.
    new_foldlevel: cy.int = 0
    new_foldlevel_copy: cy.int = 0
    new_fold_indent_spaces: cy.int = 0
    new_fold_indent_spaces_copy: cy.int = 0

    # Properties of lines and which hold across lines.
    foldlevel: cy.int = 0
    prev_foldlevel: cy.int = 0
    in_string: bint = False
    prev_in_string: bint = False
    nested: bint = False
    prev_nested: bint = False
    line_has_a_contination: bint = False
    prev_line_has_a_continuation: bint = False
    indent_spaces: cy.int = 0
    prev_indent_spaces: cy.int = 0
    escape_char: bint = False

    # String-related variables.
    in_single_quote_string: bint = False
    in_double_quote_string: bint = False
    in_single_quote_docstring: bint = False
    in_double_quote_docstring: bint = False

    def is_in_string():
        return (in_single_quote_string or in_single_quote_docstring or
                in_double_quote_string or in_double_quote_docstring)

    # Nesting in different bracket types.
    nest_parens: cy.int = 0
    nest_brackets: cy.int = 0
    nest_braces: cy.int = 0

    def is_nested():
        return nest_parens or nest_brackets or nest_braces

    # Loop over the lines.
    line_num: cy.int = -1
    buffer_len: cy.int = len(buffer_lines)
    for line_num in range(buffer_len):
        line = buffer_lines[line_num]

        ends_with_triple_quote: bint
        ends_with_colon: bint
        begins_with_triple_quote: bint
        indent_spaces: cy.int
        last_non_whitespace_index: cy.int
        line_is_only_comment: bint
        is_empty: bint

        if prev_line_has_a_continuation:
            indent_spaces = 0
            line_is_only_comment = False
        else:
            ends_with_triple_quote = False
            ends_with_colon = False
            begins_with_triple_quote = False
            indent_spaces = 0
            line_is_only_comment = False
            is_empty = False

        line_len: cy.int = len(line)

        # Find the indent level and identify empty strings.
        i: cy.int = -1
        for i in range(line_len):
            char = line[i]
            if char != " " and char != "\t":
                indent_spaces = i
                if not in_string and char == "#":
                    line_is_only_comment = True
                break
        else: # nobreak
            is_empty = True

        # Find the index of the last non-whitespace char (but might be in comment).
        last_non_whitespace_index = -1 # Means empty, be careful if indexing.
        if not is_empty:
            for i in range(line_len-1, -1, -1): # Search backward in line.
                char = line[i]
                if char != " " and char != "\t":
                    last_non_whitespace_index = i
                    break

        # Loop over the rest of the chars in the line.
        i = indent_spaces - 1
        while not is_empty and not line_is_only_comment: # Loop, but ignore empty lines.
            i += 1
            if i > last_non_whitespace_index:
                break
            char = line[i]

            in_string = is_in_string()
            nested = is_nested()

            # String escape char.
            if char == "\\" and not escape_char:
                if in_string:
                    escape_char = True
                    continue # Note, we stop processing here and pick up on next loop through.
                break # Line continuation, pick up on next line like on this one.
            char_is_escaped = escape_char
            escape_char = False

            # Turn off `ends_with_triple_quote` and `ends_with_colon` if non-whitespace char.
            if char != " " and char != "\t" and char != "#":
                # Char is # handles the weird case of `""" # comment`
                ends_with_triple_quote = False
                ends_with_colon = False

            if char == ":" and not in_string and not nested:
                ends_with_colon = True # Will toggle back off of something else found.

            # Comments on lines, after code.
            elif not in_string and char == "#":
                # Note this break keeps the current ends_with_triple_quote setting as final.
                break # We're finished processing the line.

            # Strings.
            elif char == '"' and not char_is_escaped:
                if i + 2 < line_len and line[i+1] == '"' and line[i+2] == '"':
                    if in_double_quote_docstring or not in_string:
                        if in_string:
                            ends_with_triple_quote = True # Provisional; may turn back off.
                        elif (not in_string and i == indent_spaces
                                            and not prev_line_has_a_continuation):
                            begins_with_triple_quote = True
                        in_double_quote_docstring = not in_double_quote_docstring
                    i += 2
                elif in_double_quote_string or not in_string:
                    in_double_quote_string = not in_double_quote_string
                continue
            elif char == "'" and not char_is_escaped:
                if i + 2 < line_len and line[i+1] == "'" and line[i+2] == "'":
                    if in_single_quote_docstring or not in_string:
                        if in_string:
                            ends_with_triple_quote = True # Provisional; may turn back off.
                        elif (not in_string and i == indent_spaces
                                            and not prev_line_has_a_continuation):
                            begins_with_triple_quote = True
                        in_single_quote_docstring = not in_single_quote_docstring
                    i += 2
                elif in_single_quote_string or not in_string:
                    in_single_quote_string = not in_single_quote_string
                continue

            if in_string: # No characters in strings matter except end quotes and escapes.
                continue

            if char == "(": nest_parens += 1; continue
            elif char == ")": nest_parens -= 1; continue
            if char == "[": nest_brackets += 1; continue
            elif char == "]": nest_brackets -= 1; continue
            if char == "(": nest_braces += 1; continue
            elif char == ")": nest_braces -= 1; continue

            if prev_line_has_a_continuation:
                indent_spaces = prev_indent_spaces
        #
        # Back in loop over lines; calculate foldlevel for the line based on computed info.
        #

        # Look for backslash line continuation at the end.
        line_has_a_contination = line and line[-1] == "\\"

        # Consolidate the separate variables checking if in a string or inside brackets.
        in_string = is_in_string()
        nested = is_nested()

        # Handle dedents from the previous line.
        #
        # Only code not in brackets of some sort should trigger a dedent.  Note comments
        # are allowed to trigger a dedent (no check for line_is_only_comment).
        dedent: bint = (not prev_in_string and not prev_nested
                        and not is_empty and (prev_indent_spaces > indent_spaces))
        if DEBUG:
            print("\n|{:<5}|".format(line_num), line, "\n", sep="")
            print("   dedent=", dedent, "  prev_indent_spaces=",
                    prev_indent_spaces, "  indent_spaces=", indent_spaces, "  is_empty=",
                    is_empty, "  line_is_only_comment=", line_is_only_comment,
                    "\n   nested=", nested, "  in_string=", in_string, sep="")
        if dedent:
            # Revert to previous foldlevel, according to how far the dedent went.
            if indent_spaces < fold_indent_spaces_stack[-1]:
                while (len(fold_indent_spaces_stack) >= 1
                        and indent_spaces < fold_indent_spaces_stack[-1]):
                    #print("POPPING stacks, indent and foldlevel are:",
                    #      fold_indent_spaces_stack, foldlevel_stack)
                    ind = fold_indent_spaces_stack.pop()
                    fld = foldlevel_stack.pop()
                    #print("POPPED foldlevel_stack", ind, fld)
                prev_indent_spaces = fold_indent_spaces_stack[-1]
                prev_foldlevel = foldlevel_stack[-1]
                #print("set prev_foldlevel to", prev_foldlevel)
                if DEBUG:
                    print("   <-- decreasing foldlevel to {}".format(prev_foldlevel))

        #
        # Begin setting the foldlevels for various cases.
        #

        foldlevel = prev_foldlevel # The fallback value.

        if is_empty:
            foldlevel = -5 # The -5 value is later be replaced by the succeeding foldlevel.

        if not is_empty or prev_line_has_a_continuation:
            # This part is the finite-state machine handling docstrings after fundef.
            begin_fun_or_class_def = is_begin_fun_or_class_def(line, prev_nested,
                                                               in_string, indent_spaces)
            if DEBUG:
                print("   begin_fun_or_class_def:", begin_fun_or_class_def)
                print("   inside_fun_or_class_def:", inside_fun_or_class_def)
                print("   just_after_fun_or_class_def:", just_after_fun_or_class_def)
                print("   inside_docstring:", inside_docstring)
                print("   just_after_fun_docstring:", just_after_fun_docstring)
                print("   foldlevel_stack and fold_indent_spaces_stack:", foldlevel_stack,
                                                                  fold_indent_spaces_stack)

            if just_after_fun_docstring:
                # Can occur at the same time as begin_fun_or_class_def: fundef after docstring.
                just_after_fun_docstring = False
                if not dedent: # Catch the case of fun with only docstring, no code.
                    foldlevel = increase_foldlevel(foldlevel_stack,
                                                   fold_indent_spaces_stack,
                                                   new_foldlevel_copy,
                                                   new_fold_indent_spaces_copy)

            if inside_docstring:
                if not in_string: # Docstring closed at end of line, repeat until.
                    inside_docstring = False
                    just_after_fun_docstring = True

            if just_after_fun_or_class_def:
                just_after_fun_or_class_def = False

                # Copy the variables new_indent spaces and new_foldlevel so that if a new
                # begin_fun_or_class_def is processed it does not overwrite them.
                new_fold_indent_spaces_copy = new_fold_indent_spaces
                new_foldlevel_copy = new_foldlevel

                if begins_with_triple_quote:
                    if in_string:
                        inside_docstring = True
                    elif ends_with_triple_quote:
                        # Trigger just_after_fun_docstring, but on next line.
                        just_after_fun_docstring = True
                    else:
                        # Syntax error or single-quote docstring.
                        foldlevel = increase_foldlevel(foldlevel_stack,
                                                       fold_indent_spaces_stack,
                                                       new_foldlevel_copy,
                                                       new_fold_indent_spaces_copy)
                else:
                    # Function with no docstring.
                    foldlevel = increase_foldlevel(foldlevel_stack,
                                                   fold_indent_spaces_stack,
                                                   new_foldlevel_copy,
                                                   new_fold_indent_spaces_copy)

            if inside_fun_or_class_def:
                if not nested and not line_has_a_contination:
                    inside_fun_or_class_def = False
                    just_after_fun_or_class_def = ends_with_colon

            if begin_fun_or_class_def:
                # Note this can be True at same time as either just_after_fun_or_class_def
                # or just_after_fun_docstring (i.e., fundef right after fundef).  Hence the
                # copies of new_foldlevel and new_fold_indent_spaces lines values to set in the
                # just_after_fun_or_class_def state.

                if nested or in_string or line_has_a_contination:
                    inside_fun_or_class_def = True
                else:
                    just_after_fun_or_class_def = True

                # New foldlevels, but application deferred until after possibly
                # processing-off a # docstring following the function def.
                curr_foldlevel: cy.int = foldlevel_stack[-1]
                new_fold_indent_spaces = indent_spaces + shiftwidth
                foldlevel_increment: cy.int = get_foldlevel_increment(curr_foldlevel,
                                                           indent_spaces, shiftwidth)
                new_foldlevel = curr_foldlevel + foldlevel_increment

        # Save the calculated foldlevel value in the cache.
        foldlevel_cache[line_num] = foldlevel

        # If foldlevel isn't -5, go back and turn immediately-preceding -5 vals to foldlevel.
        if foldlevel != -5:
            replace_preceding_minus_five_foldlevels(foldlevel_cache, line_num-1, foldlevel)

        # Final var updates for properties across lines, to setup for next line in loop.
        prev_foldlevel = foldlevel if not is_empty else prev_foldlevel
        prev_nested = nested
        prev_in_string = in_string
        prev_indent_spaces = (indent_spaces if not is_empty and not line_is_only_comment
                              else prev_indent_spaces)
        prev_line_has_a_continuation = line_has_a_contination

    # Handle the case where foldlevel of last line was set to -5; replace sequence with 0.
    if foldlevel_cache[line_num] == -5:
        replace_preceding_minus_five_foldlevels(foldlevel_cache, line_num, 0)


