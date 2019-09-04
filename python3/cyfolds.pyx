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
     |                |<---------------------- inside_fun_or_class_docstring
     |                |
     |                |
     |      just_after_fun_or_class_docstring
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
  Downside is that folds inside, say, a high-foldlevel "if" statement will also
  be unfolded, even if they are def, class, etc.  Would work better for docstrings
  if you could force an artificial dedent after it (since it doesn't nest).

* Add a list type for high-foldlevel jump keywords::

     let g:cyfolds_fold_keywords = ['def', 'async def', 'class', 'cdef']
     let g"cyfolds_high_foldlevel_keywords = ['if', 'for', 'while']

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
  search or hash over the whole file to tell what changed.  Updating is a pain
  with blocks.

* Maybe have an option to number indents sequentially instead of number of
  spaces.  Might be more like what some people expect, maybe not.  Number by
  indents (current way) seems more intuitive to me.

* Set up a test suite, at least for the Python code part.

"""

DEBUG: bint = False
TESTING: bint = False
USE_CACHING: bint = True
EXPERIMENTAL: bint = False

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

import sys
from collections import namedtuple
from typing import List, Tuple, Set, Dict
import re

import cython as cy
from cpython cimport bool # Use Python bool.
from cython import bint # C int coerced to bool.
#from cpython cimport int # Use Python int.

buffer_change_indicator_dict: Dict[cy.int, cy.int] = {} # Digested states, by buffer number.
foldlevel_cache: Dict[cy.int, List[cy.int]] = {} # Cache of foldlevel values, by buffer num.
config_var_settings: (cy.int, cy.int, cy.int, cy.int) = (-2, -2, -2, -2) # Dirty if config change.

recalcs: cy.int = 0 # Global counting the number of recalculations (for debugging).
foldfun_calls: cy.int = 0 # Global counting the number of calls to get_foldlevel (debugging).

saved_buffer_lines_dict: Dict(cy.int, List(str)) = {} # Hashes indexed by buffer number.

fold_keywords_matcher = None # Global later set to a compiled regex that matches keywords.
default_fold_keywords: str = "class,def,cdef,cpdef,async def"

def get_foldlevel(lnum: cy.int, cur_buffer_num: cy.int, cur_undo_sequence:cy.int=-1,
                  foldnestmax:cy.int=20, shiftwidth:cy.int=4,
                  lines_of_module_docstrings:cy.int=-1, lines_of_fun_and_class_docstrings:cy.int=-1,
                  test_buffer=None):
    """Recalculate all the fold levels for line `lnum` and greater.  Note that this
    function is passed to vim, and expects `lnum` to be numbered from 1 rather than
    zero.  The `test_buffer` if for passing in a mock of the `vim.current.buffer`
    object in debugging and testing.

    Values are cached and cached values are returned if the buffer-change
    indicator does not indicate changes.

    The -1 value for cur_undo_sequence represents a None value, and means to use
    hashing instead for dirty-cache change detection."""
    # Be SURE that all int args passed to this function have been converted from strings.
    global recalcs, foldfun_calls # Debugging counts, persistent.
    global saved_buffer_lines_dict, config_var_settings
    if fold_keywords_matcher is None:
        setup_regex_pattern()
    new_config_var_settings: (cy.int, cy.int, cy.int, cy.int)
    new_config_var_settings = foldnestmax, shiftwidth, lines_of_module_docstrings, lines_of_fun_and_class_docstrings

    lnum -= 1 # Compensate for different numbering convention, vim vs. Python.

    if not TESTING:
        vim_buffer_lines = vim.current.buffer
    else:
        vim_buffer_lines = test_buffer

    dirty_cache: bint
    if USE_CACHING:
        if config_var_settings != new_config_var_settings:
            dirty_cache = True
            config_var_settings = new_config_var_settings
        elif EXPERIMENTAL:
            # Beginnings of an experiment in finding the exact change lines by
            # saving lines or line hashes.  Would make for faster updates if
            # you also save enough state to jump into calculate_foldlevels in
            # the middle of the file.
            #
            # Note, maybe combine with using the cur_undo_sequence as the hash
            # and then only search to find diffs when those don't match, so
            # only do this stuff on dirty cache event, not here.
            dirty_cache = True
            saved_buffer_lines = saved_buffer_lines_dict.get(cur_buffer_num, [])
            if saved_buffer_lines:
                vim_buffer_lines_len: cy.int = len(vim_buffer_lines)
                saved_buffer_lines_len: cy.int = len(saved_buffer_lines)
                dirty_cache: bint = (saved_buffer_lines_len != vim_buffer_lines_len
                                     or any(saved_buffer_lines[i] != vim_buffer_lines[i]
                                     for i in range(vim_buffer_lines_len)))
        else:
            if cur_undo_sequence == -1:
                # Convert the buffer into an ordinary list of strings, for easier Cython.
                buffer_lines = tuple(i for i in vim_buffer_lines)
                compacted_buffer_state: cy.int = hash(buffer_lines) # NOTE: really Py_ssize_t
            else:
                compacted_buffer_state: cy.int = cur_undo_sequence

            dirty_cache = compacted_buffer_state != buffer_change_indicator_dict.get(
                                                                 cur_buffer_num, -1)
            buffer_change_indicator_dict[cur_buffer_num] = compacted_buffer_state
    else:
        dirty_cache = True
    #print(" buffer_change_indicator_dict=", buffer_change_indicator_dict[cur_buffer_num], " dirty=", dirty_cache, " calls=",
    #        foldfun_calls, " cur_buffer_num=", cur_buffer_num, type(cur_buffer_num), sep="")

    #print("updating folds========================================================begin", foldfun_calls)
    if dirty_cache:
        #print("updating folds, dirty........................................................", recalcs)
        # Get a new foldlevel_cache list and recalculate all the foldlevels.
        new_cache_list: List[cy.int] = [0] * len(vim_buffer_lines)
        foldlevel_cache[cur_buffer_num] = new_cache_list
        calculate_foldlevels(new_cache_list, vim_buffer_lines, shiftwidth,
                             lines_of_module_docstrings, lines_of_fun_and_class_docstrings)
        recalcs += 1
        #print("done with folds.......................................................done", recalcs)
        if EXPERIMENTAL:
            saved_buffer_lines_dict[cur_buffer_num] = [i for i in vim_buffer_lines]

    foldlevel = foldlevel_cache[cur_buffer_num][lnum]
    #foldlevel = min(foldlevel, foldnestmax)
    foldfun_calls += 1
    return foldlevel

def delete_buffer_cache(buffer_num: cy.int):
    """Remove the saved cache information for the buffer with the given number.
    This is meant to be called when the buffer is closed, to avoid wasting
    memory."""
    # This function is getting called twice for some reason, so check for the key before del.
    if buffer_num in buffer_change_indicator_dict:
        del buffer_change_indicator_dict[buffer_num]
    if buffer_num in foldlevel_cache:
        del foldlevel_cache[buffer_num]

keyword_pattern_dict: Dict[str,str] = {"else": "else:",
                                       "try": "try:",
                                       "finally": "finally:",
                                       "except": "except |except:",
                                      }

def setup_regex_pattern(fold_keywords_string: str=default_fold_keywords):
    """Set up the regex to match the keywords in the list `pat_list`.  The
    `pat_string` should be a comma-separated list of keywords."""
    global fold_keywords_matcher

    keywords_list: List[str] = fold_keywords_string.split(",")
    keywords_list = [keyword_pattern_dict.get(k, k + " ") for k in keywords_list]
    pattern_string: str = "|".join(keywords_list)

    fold_keywords_matcher = re.compile(r"(?P<keyword>{})".format(pattern_string))

cdef bint is_begin_fun_or_class_def(line: str, prev_nested: cy.int,
                                    in_string: cy.int, indent_spaces: cy.int):
    """Boolean for whether fun or class def begins on the line."""
    if prev_nested or in_string:
        return False
    ## This alternative seems to run at about the same speed as the regex.
    ## Keyword list would need to be set up differently for it, though.
    #use_startswith: bint = True
    #if use_startswith:
    #    keywords_list: List[str] = ["def ", "class "]
    #    k: str
    #    for k in keywords_list:
    #        if line.startswith(k, indent_spaces):
    #            return True
    #            break
    #    else:
    #        return = False

    max_pat_len: cy.int = 8 # Largest keyword pattern ('finally:').
    # Passing a slice vs. setting the pos and endpos seems to make no real difference in time.
    #matchobject = re.match(fold_keywords_matcher, line[indent_spaces:indent_spaces+max_pat_len])
    matchobject = fold_keywords_matcher.match(line, indent_spaces, indent_spaces+max_pat_len)
    if matchobject:
        return True
    else:
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
    if DEBUG:
        print("   --> increasing foldlevel to {}".format(new_foldlevel))

    if new_foldlevel > foldlevel_stack[-1]:
        foldlevel_stack.append(new_foldlevel)
        fold_indent_spaces_stack.append(new_fold_indent_spaces)
    return new_foldlevel

cdef (cy.int, cy.int) decrease_foldlevel(indent_spaces: cy.int,
                                         fold_indent_spaces_stack: List[cy.int],
                                         foldlevel_stack: List[cy.int], docstring:bint=False):
    """Revert to previous foldlevel, according to how far the dedent went.  Return
    the new `prev_indent_spaces` and `prev_foldlevel`."""
    if not docstring:
        while (len(fold_indent_spaces_stack) >= 1
                and indent_spaces < fold_indent_spaces_stack[-1]):
            fold_indent_spaces_stack.pop()
            foldlevel_stack.pop()
    else:
        fold_indent_spaces_stack.pop()
        foldlevel_stack.pop()
    prev_indent_spaces = fold_indent_spaces_stack[-1]
    prev_foldlevel = foldlevel_stack[-1]
    if DEBUG:
        print("   <-- decreasing foldlevel to {}".format(prev_foldlevel))
    return prev_indent_spaces, prev_foldlevel

cdef (cy.int, cy.int) get_new_foldlevel(foldlevel_stack: List[cy.int], indent_spaces: cy.int,
                                        shiftwidth: cy.int, docstring:bint=False):
    """Return the new foldlevel and the new shiftlevel."""
    curr_foldlevel: cy.int = foldlevel_stack[-1]
    new_foldlevel: cy.int
    new_fold_indent_spaces: cy.int

    # This method gives foldlevels that are identical to indent levels, except docstrings.
    new_foldlevel = indent_spaces // shiftwidth + 1 # Just add one to old one for sequential...
    if docstring:
        new_foldlevel += 1
    new_fold_indent_spaces = indent_spaces + shiftwidth
    #if not docstring:
    #    increment = indent_spaces - curr_foldlevel + shiftwidth
    #else:
    #    increment = indent_spaces - curr_foldlevel + 1 # TODO divide indent_spaces by shiftwidth again
    #if not docstring: assert increment >= 0
    #return curr_foldlevel + increment, indent_spaces + shiftwidth
    return new_foldlevel, new_fold_indent_spaces

cdef bint is_in_string(in_single_quote_string: bint, in_single_quote_docstring: bint,
                 in_double_quote_string: bint, in_double_quote_docstring: bint):
    """Combine the separate string conditions into a single in-string condition."""
    return (in_single_quote_string or in_single_quote_docstring or
            in_double_quote_string or in_double_quote_docstring)

cdef cy.int is_nested(nest_parens: cy.int, nest_brackets: cy.int, nest_braces: cy.int):
    """Combine the separate nesting levels into a single test for nestedness."""
    return nest_parens or nest_brackets or nest_braces

cdef void calculate_foldlevels(foldlevel_cache: List[cy.int], buffer_lines: List[str],
                               shiftwidth: cy.int, lines_of_module_docstrings:cy.int,
                               lines_of_fun_and_class_docstrings: cy.int):
    """Do the actual calculations and return the foldlevel."""
    # States in the state machine.
    inside_fun_or_class_def: bint = False
    just_after_fun_or_class_def: bint = False
    inside_fun_or_class_docstring: bint = False
    just_after_fun_or_class_docstring: bint = False

    # Stacks holding the current foldlevels and their indents, highest on top.
    foldlevel_stack: List[cy.int] = [0]
    fold_indent_spaces_stack: List[cy.int] = [0]

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
    processing_docstring_indent: bint = False

    # String-related variables.
    in_single_quote_string: bint = False
    in_double_quote_string: bint = False
    in_single_quote_docstring: bint = False
    in_double_quote_docstring: bint = False

    # Nesting in different bracket types.
    nest_parens: cy.int = 0
    nest_brackets: cy.int = 0
    nest_braces: cy.int = 0

    # New foldlevels and copies saved to avoid overwrites.
    new_foldlevel: cy.int = 0
    new_foldlevel_copy: cy.int = 0
    new_fold_indent_spaces: cy.int = 0
    new_fold_indent_spaces_copy: cy.int = 0

    # Some counts for folding docstrings.
    lines_since_begin_triple: cy.int = -1 # Lines since begins_with_triple_quote was True.
    lines_since_end_triple: cy.int = -1 # Lines since ends_with_triple_quote was True.

    # Loop over the lines.
    line_num: cy.int = -1
    buffer_len: cy.int = len(buffer_lines)
    for line_num in range(buffer_len):
        line = buffer_lines[line_num]

        begins_with_triple_quote: bint # Begins with non-nested, not-in-string triple quote.
        ends_with_triple_quote: bint   # Ends with non-nested, in-string triple quote.
        ends_with_colon: bint          # Ends with non-nested, not-in-string colon.
        indent_spaces: cy.int          # The number of spaces the line is indented.
        last_non_whitespace_index: cy.int # Last non-whitespace on the line.
        line_is_only_comment: bint     # Line contains only a comment.
        is_empty: bint                 # Line is empty.

        if prev_line_has_a_continuation:
            indent_spaces = 0
            line_is_only_comment = False
        else:
            begins_with_triple_quote = False
            ends_with_triple_quote = False
            ends_with_colon = False
            indent_spaces = 0
            line_is_only_comment = False
            is_empty = False

        line_len: cy.int = len(line)

        # Go to first non-whitespce to find the indent level and identify empty strings.
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

            in_string = is_in_string(in_single_quote_string, in_single_quote_docstring,
                                     in_double_quote_string, in_double_quote_docstring)
            nested = is_nested(nest_parens, nest_brackets, nest_braces)

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
                            lines_since_begin_triple = 0
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
                            lines_since_begin_triple = 0
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

        #
        # Back in loop over lines; calculate foldlevel for the line based on computed info.
        #

        if ends_with_triple_quote:
            lines_since_end_triple = 0
        elif begins_with_triple_quote:
            lines_since_end_triple = -1 # Note that -1 is a dummy value that means "unset."

        # Now that the line is processed the indent_spaces values are just used to
        # detect dedents and set fold values.  Set the indent_spaces of continuation
        # lines and lines in strings to the previous line's indent value (the logical
        # indent value).  These propagate forward for multi-line indents and continuations.
        if prev_line_has_a_continuation or prev_in_string:
            indent_spaces = prev_indent_spaces

        # Look for backslash line continuation at the end.
        line_has_a_contination = line and line[-1] == "\\"

        # Consolidate the separate variables checking if in a string or inside brackets.
        in_string = is_in_string(in_single_quote_string, in_single_quote_docstring,
                                 in_double_quote_string, in_double_quote_docstring)
        nested = is_nested(nest_parens, nest_brackets, nest_braces)

        #
        # Handle dedents from the previous line.
        #
        # Only code not in brackets of some sort should trigger a dedent.  Note comments
        # are allowed to trigger a dedent (no check for line_is_only_comment).
        #

        # TODO: misleading names...
        physical_dedent: bint = (not prev_in_string and not prev_nested
                        and not is_empty and (prev_indent_spaces > indent_spaces))
        logical_dedent: bint = physical_dedent and indent_spaces < fold_indent_spaces_stack[-1]

        if DEBUG:
            print("\n|{:<5}|".format(line_num), line, "\n", sep="")
            print("   physical_dedent=", physical_dedent, "  logical_dedent=", logical_dedent,
                    "  prev_indent_spaces=", prev_indent_spaces, "  indent_spaces=", indent_spaces,
                    "  is_empty=", is_empty, "\n   line_is_only_comment=", line_is_only_comment,
                    "  nested=", nested, "  in_string=", in_string, "  prev_in_string=",
                    prev_in_string, "\n   begins_with_triple_quote=", begins_with_triple_quote,
                    "  lines_since_begin_triple=", lines_since_begin_triple,
                    "\n   ends_with_triple_quote=", ends_with_triple_quote,
                    "  lines_since_end_triple=", lines_since_end_triple,
                    sep="")

        if logical_dedent:
            prev_indent_spaces, prev_foldlevel = decrease_foldlevel(indent_spaces,
                                                                    fold_indent_spaces_stack,
                                                                    foldlevel_stack)

        #
        # Begin setting the foldlevels for various cases.
        #

        # Process beginning of module docstrings (and freestanding docstrings in general).
        # Sets the prev-foldlevel, since by default that will become the new foldlevel.
        if (lines_of_module_docstrings != -1 and lines_since_begin_triple == lines_of_module_docstrings
                and lines_since_end_triple == -1 and not inside_fun_or_class_docstring
                and not just_after_fun_or_class_docstring):
            processing_docstring_indent = True
            new_foldlevel, new_fold_indent_spaces = get_new_foldlevel(foldlevel_stack,
                                              indent_spaces, shiftwidth, docstring=True)
            prev_foldlevel = increase_foldlevel(foldlevel_stack,
                                                fold_indent_spaces_stack,
                                                new_foldlevel,
                                                new_fold_indent_spaces)

        # Process the end of module docstrings.
        if processing_docstring_indent and lines_since_end_triple == 0: #ends_with_triple_quote:
            # To not keep closing """ above, use lines_since_end_triple == 1, not 0.
            processing_docstring_indent = False
            _prev_indent_spaces: cy.int
            _prev_indent_spaces, prev_foldlevel = decrease_foldlevel(indent_spaces,
                                                                    fold_indent_spaces_stack,
                                                                    foldlevel_stack, docstring=True)

        if DEBUG:
            print("   processing_docstring_indent=", processing_docstring_indent, sep="")

        foldlevel = prev_foldlevel # The fallback value.

        if is_empty and not in_string:
            foldlevel = -5 # The -5 value is later be replaced by the succeeding foldlevel.

        if not is_empty or prev_line_has_a_continuation:
            # This part is the finite-state machine handling docstrings after fundef.
            begin_fun_or_class_def: bint = is_begin_fun_or_class_def(line, prev_nested,
                                                               in_string, indent_spaces)
            if DEBUG:
                print("   begin_fun_or_class_def:", begin_fun_or_class_def)
                print("   inside_fun_or_class_def:", inside_fun_or_class_def)
                print("   just_after_fun_or_class_def:", just_after_fun_or_class_def)
                print("   inside_fun_or_class_docstring:", inside_fun_or_class_docstring)
                print("   just_after_fun_or_class_docstring:", just_after_fun_or_class_docstring)
                print("   foldlevel_stack and fold_indent_spaces_stack:", foldlevel_stack,
                                                                  fold_indent_spaces_stack)

            if just_after_fun_or_class_docstring:
                # Can occur at the same time as begin_fun_or_class_def: fundef after docstring.
                just_after_fun_or_class_docstring = False
                # TODO: Locical dedent fails on below line, folds empty... why?
                if not physical_dedent: # Catch the case of fun with only docstring, no code.
                    foldlevel = increase_foldlevel(foldlevel_stack,
                                                   fold_indent_spaces_stack,
                                                   new_foldlevel_copy,
                                                   new_fold_indent_spaces_copy)

            if inside_fun_or_class_docstring:
                if lines_of_fun_and_class_docstrings == 1:
                    inside_fun_or_class_docstring = False
                    foldlevel = increase_foldlevel(foldlevel_stack,
                                                   fold_indent_spaces_stack,
                                                   new_foldlevel_copy,
                                                   new_fold_indent_spaces_copy)
                elif not in_string or ( # Docstring closed at end of line, repeat until.
                        lines_of_fun_and_class_docstrings != -1 and
                        lines_since_begin_triple >= lines_of_fun_and_class_docstrings-1):
                    inside_fun_or_class_docstring = False
                    just_after_fun_or_class_docstring = True

            if just_after_fun_or_class_def:
                just_after_fun_or_class_def = False

                # Copy the variables new_indent spaces and new_foldlevel so that if a new
                # begin_fun_or_class_def is processed it does not overwrite them.
                new_fold_indent_spaces_copy = new_fold_indent_spaces
                new_foldlevel_copy = new_foldlevel

                if begins_with_triple_quote and lines_of_fun_and_class_docstrings != 0:
                    if in_string:
                        inside_fun_or_class_docstring = True
                    elif ends_with_triple_quote:
                        # Trigger just_after_fun_or_class_docstring, but on next line.
                        just_after_fun_or_class_docstring = True
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
                # Note this can be True at same time as either just_after_fun_or_class_def or
                # just_after_fun_or_class_docstring (i.e., fundef right after fundef).  Hence
                # the copies of new_foldlevel and new_fold_indent_spaces lines values to set in
                # the just_after_fun_or_class_def state.
                if nested or in_string or line_has_a_contination:
                    inside_fun_or_class_def = True
                else:
                    just_after_fun_or_class_def = True

                # New foldlevels, but application deferred until after possibly
                # processing-off a docstring following the function def.
                new_foldlevel, new_fold_indent_spaces = get_new_foldlevel(foldlevel_stack,
                                                                 indent_spaces, shiftwidth)

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

        if lines_since_begin_triple >= 0:
            lines_since_begin_triple += 1
        if lines_since_end_triple >= 0:
            lines_since_end_triple += 1

    # Handle the case where foldlevel of last line was set to -5; replace sequence with 0.
    if foldlevel_cache[line_num] == -5:
        replace_preceding_minus_five_foldlevels(foldlevel_cache, line_num, 0)


