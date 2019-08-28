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

* The vim python API docs (same as ':help python'):
  https://docs.huihoo.com/vim/7.2/if_pyth.htm

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

:undolist

:changes

:echo undotree()  # This is the one, returns a dict!  Look at keys and entried.
:help undotree()

fun s:GetChangeFromSaveNr(saved)
	for item in undotree().entries
		if has_key(item, "save") && item.save == a:saved
			let save_change = item.seq
			break
		endif
	endfor
	return save_change
endfun

To get the time of a change:
 :echo undotree().entries[0].time     zero element of list, time key


Passing dicts to python?
------------------------

These are general docs of Python interface to vim (same as :help python)
    https://vimhelp.org/if_pyth.txt.html
    To facilitate bi-directional interface, you can use pyeval() and py3eval()
    functions to evaluate Python expressions and pass their values to Vim
    script.  pyxeval() is also available.

    The Python value "None" is converted to v:none.

Answer in above docs:
    vim.bindeval objects

vim.vars                                                python-vars
vim.vvars                                               python-vvars
        Dictionary-like objects holding dictionaries with global (g:) and
        vim (v:) variables respectively. Identical to vim.bindeval("g:"),
        but faster.

7. vim.bindeval objects                         python-bindeval-objects

vim.Dictionary object                           python-Dictionary
    Dictionary-like object providing access to vim Dictionary type.
    Attributes:
        Attribute  Description
        locked     One of                       python-.locked
                    Value           Description
                    zero            Variable is not locked
                    vim.VAR_LOCKED  Variable is locked, but can be unlocked
                    vim.VAR_FIXED   Variable is locked and can't be unlocked
                   Read-write. You can unlock locked variable by assigning
                   True or False to this attribute. No recursive locking
                   is supported.
        scope      One of
                    Value              Description
                    zero               Dictionary is not a scope one
                    vim.VAR_DEF_SCOPE  g: or l: dictionary
                    vim.VAR_SCOPE      Other scope dictionary,
                                       see internal-variables
    Methods (note: methods do not support keyword arguments):
        Method      Description
        keys()      Returns a list with dictionary keys.
        values()    Returns a list with dictionary values.
        items()     Returns a list of 2-tuples with dictionary contents.
        update(iterable), update(dictionary), update(**kwargs)
                    Adds keys to dictionary.
        get(key[, default=None])
                    Obtain key from dictionary, returning the default if it is
                    not present.
        pop(key[, default])
                    Remove specified key from dictionary and return
                    corresponding value. If key is not found and default is
                    given returns the default, otherwise raises KeyError.
        popitem()
                    Remove random key from dictionary and return (key, value)
                    pair.
        has_key(key)
                    Check whether dictionary contains specified key, similar
                    to `key in dict`.

        __new__(), __new__(iterable), __new__(dictionary), __new__(update)
                    You can use vim.Dictionary() to create new vim
                    dictionaries. d=vim.Dictionary(arg) is the same as
                    d=vim.bindeval('{}');d.update(arg). Without arguments
                    constructs empty dictionary.

    Examples:
        d = vim.Dictionary(food="bar")          # Constructor
        d['a'] = 'b'                            # Item assignment
        print d['a']                            # getting item
        d.update({'c': 'd'})                    # .update(dictionary)
        d.update(e='f')                         # .update(**kwargs)
        d.update((('g', 'h'), ('i', 'j')))      # .update(iterable)
        for key in d.keys():                    # .keys()
        for val in d.values():                  # .values()
        for key, val in d.items():              # .items()
        print isinstance(d, vim.Dictionary)     # True
        for key in d:                           # Iteration over keys
        class Dict(vim.Dictionary):             # Subclassing

    Note: when iterating over keys you should not modify dictionary.

vim.List object                                 python-List
    Sequence-like object providing access to vim List type.
    Supports .locked attribute, see python-.locked. Also supports the
    following methods:
        Method          Description
        extend(item)    Add items to the list.

        __new__(), __new__(iterable)
                        You can use vim.List() to create new vim lists.
                        l=vim.List(iterable) is the same as
                        l=vim.bindeval('[]');l.extend(iterable). Without
                        arguments constructs empty list.
    Examples:
        l = vim.List("abc")             # Constructor, result: ['a', 'b', 'c']
        l.extend(['abc', 'def'])        # .extend() method
        print l[1:]                     # slicing
        l[:0] = ['ghi', 'jkl']          # slice assignment
        print l[0]                      # getting item
        l[0] = 'mno'                    # assignment
        for i in l:                     # iteration
        print isinstance(l, vim.List)   # True
        class List(vim.List):           # Subclassing


Basic dirty cache detect (save fancy for later)
-----------------------------------------------

To get timestamp of last entry in the undotree:

    :undotree().entries[undotree().seq_cur].time

"""

# TODO, maybe: Add options to also fold for, while, if, with, and try.  Have a
# function that is passed the arguments for what to fold which then sets and
# compiles a global regex to use.  They mostly work now, but not all cases.
# Also, cdef for Python code.

# TODO: Make sure line ends in semicolon at end of fundef, while, etc., just
# as an extra check that's easy to do.  Otherwise, don't do new fold.

DEBUG: bint = False
TESTING: bint = False
USE_CACHING = True

try:
    import vim
except ImportError:
    TESTING = True

if TESTING:
    # These classes mock vim.buffer.current for testing.
    class Current:
        buffer = []
    class vim:
        current = Current

from collections import namedtuple
from typing import List, Tuple, Set
import numpy as np

import cython as cy
from cpython cimport bool # Use Python bool.
from cython import bint # C int coerced to bool.
#from cpython cimport int # Use Python int.

prev_buffer_hash: cy.int = 0
foldlevel_cache: List[cy.int] = [] # Cache of all the computed foldlevel values.
recalcs: cy.int = 0 # Global counting the number of recalculations (for debugging).

def foldlevel(lnum: int, foldnestmax: int, shiftwidth:int=4, test_buffer=None):
    """Recalculate all the fold levels for line `lnum` and greater.  Note that this
    function is passed to vim, and expects `lnum` to be numbered from 1 rather than
    zero.  The `test_buffer` if for passing in a mock of the `vim.current.buffer`
    object in debugging and testing."""
    global foldlevel_cache, prev_buffer_hash, recalcs

    foldnestmax = int(foldnestmax)
    shiftwidth = int(shiftwidth)
    lnum = int(lnum) - 1 # Compensate for different numbering convention.

    if not TESTING:
        buffer_lines = vim.current.buffer
    else:
        buffer_lines = test_buffer

    # Convert the buffer into an ordinary list of strings, for easier Cython.
    buffer_lines = [i for i in buffer_lines]
    assert buffer_lines

    if USE_CACHING:
        buffer_hash = hash(tuple(buffer_lines))
        dirty_cache = buffer_hash != prev_buffer_hash
        prev_buffer_hash = buffer_hash
    else:
        dirty_cache = True

    if dirty_cache:
        # Get a new foldlevel_cache list and recalculate all the foldlevels.
        foldlevel_cache = [0] * len(buffer_lines)
        calculate_foldlevels(foldlevel_cache, buffer_lines, shiftwidth)
        recalcs += 1

    foldlevel = foldlevel_cache[lnum]
    #foldlevel = min(foldlevel, foldnestmax)
    return foldlevel

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

cdef cy.int increase_foldlevel(foldlevel_stack: List[cy.int], indent_spaces_stack: List[cy.int],
                               new_foldlevel_queue: List[cy.int],
                               new_indent_spaces_queue: List[cy.int]):
    """The fun/class defs define the new fold levels, but they're deferred for possible
    docstrings.  Also, levels are saved so things which
    dedent can return to that level (like after nested fun defs)."""
    new_indent_spaces = new_indent_spaces_queue.pop()
    new_foldlevel = new_foldlevel_queue.pop()
    if DEBUG:
        print("   --> increasing foldlevel to {}".format(new_foldlevel))
    if new_foldlevel != foldlevel_stack[-1] + 1:
        print("ASSERTION FAILED: pushing new foldlevel {} on stack with {} on top."
              .format(new_foldlevel, foldlevel_stack[-1]))
    if len(new_foldlevel_queue) > 2:
        print("ASSERTION FAILED: extra elements on new_foldlevel_queue:",
              new_foldlevel_queue)
    if new_foldlevel > foldlevel_stack[-1]:
        foldlevel_stack.append(new_foldlevel)
        indent_spaces_stack.append(new_indent_spaces)
    return new_foldlevel


cdef void calculate_foldlevels(foldlevel_cache: List[cy.int], buffer_lines: List[str],
                               shiftwidth: cy.int):
    """Do the actual calculations and return the foldlevel."""

    in_single_quote_string: bint = False
    in_double_quote_string: bint = False
    in_single_quote_docstring: bint = False
    in_double_quote_docstring: bint = False

    def is_in_string():
        return (in_single_quote_string or in_single_quote_docstring or
                in_double_quote_string or in_double_quote_docstring)

    nest_parens: cy.int = 0
    nest_brackets: cy.int = 0
    nest_braces: cy.int = 0

    def is_nested():
        return nest_parens or nest_brackets or nest_braces

    inside_fun_or_class_def: bint = False
    just_after_fun_or_class_def: bint = False
    inside_docstring: bint = False
    just_after_fun_docstring: bint = False

    foldlevel: cy.int = 0
    prev_foldlevel: cy.int = 0
    nested: bint = False
    prev_nested: bint = False
    indent_spaces: cy.int = 0
    prev_indent_spaces: cy.int = 0
    in_string: bint = False
    escape_char: bint = False
    prev_in_string: bint = False
    line_has_a_contination: bint = False
    line_is_a_continuation: bint = False

    foldlevel_stack: List[cy.int] = [0] # Stack of foldlevels with each increase.
    indent_spaces_stack: List[cy.int] = [0] # Corresponding stack of indent levels.

    new_foldlevel_queue: List[cy.int] = []
    new_indent_spaces_queue: List[cy.int] = []

    for line_num, line in enumerate(buffer_lines):
        ends_in_triple_quote: bint = False
        begins_with_triple_quote: bint = False
        indent_spaces: cy.int = 0
        found_indent_spaces: bint = False
        line_is_only_comment: bint = False
        is_empty: bint = False

        line_len: cy.int = len(line)
        if line == "": # Was rstripped.
            assert line_len == 0
            indent_spaces: cy.int = 0
            is_empty = True
            line_is_only_comment = False

        # Loop over the chars in the line.
        i: cy.int = -1
        while not is_empty: # Loop, but ignore empty lines.
            i += 1
            if i >= line_len:
                break

            in_string = is_in_string()
            nested = is_nested()

            char = line[i]

            # Set the indent level as the first non-whitespace char index.
            if char != " " and char != "\t":
                if char != "#": # Below will handle the weird case of `""" # comment`
                    ends_in_triple_quote = False # Turn off; found non-whitespace non-comment.
                # Below conditional only runs up to first non-whitespace, to find indent.
                if not found_indent_spaces:
                    indent_spaces = i
                    found_indent_spaces = True
                    if not in_string and char == "#": # First char is comment char.
                        line_is_only_comment = True
                        break # Comments make no difference, done processing.

            # Comments on lines, after code.
            if not in_string and char == "#":
                # Note this break keeps the current ends_in_triple_quote setting as final.
                break # We're finished processing the line.

            # Escape char.
            if in_string and char == "\\" and not escape_char:
                escape_char = True
                continue # Note, we stop processing here and pick up on next loop through.
            char_is_escaped = escape_char
            escape_char = False

            # Strings.
            if char == '"' and not char_is_escaped:
                if i + 2 < line_len and line[i+1] == '"' and line[i+2] == '"':
                    if in_double_quote_docstring or not in_string:
                        if in_string:
                            ends_in_triple_quote = True # Provisional; may turn back off.
                        elif not in_string and i == indent_spaces:
                            begins_with_triple_quote = True
                        in_double_quote_docstring = not in_double_quote_docstring
                    i += 2
                elif in_double_quote_string or not in_string:
                    in_double_quote_string = not in_double_quote_string
                continue
            if char == "'" and not char_is_escaped:
                if i + 2 < line_len and line[i+1] == "'" and line[i+2] == "'":
                    if in_single_quote_docstring or not in_string:
                        if in_string:
                            ends_in_triple_quote = True # Provisional; may turn back off.
                        elif not in_string and i == indent_spaces:
                            begins_with_triple_quote = True
                        in_single_quote_docstring = not in_single_quote_docstring
                    i += 2
                elif in_single_quote_string or not in_string:
                    in_single_quote_string = not in_single_quote_string
                continue

            if in_string: # No characters in strings matter but quotes and escapes.
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
            if indent_spaces < indent_spaces_stack[-1]:
                while len(indent_spaces_stack) >= 1 and indent_spaces < indent_spaces_stack[-1]:
                    #print("POPPING stacks, indent and foldlevel are:",
                    #      indent_spaces_stack, foldlevel_stack)
                    ind = indent_spaces_stack.pop()
                    fld = foldlevel_stack.pop()
                    #print("POPPED foldlevel_stack", ind, fld)
                prev_indent_spaces = indent_spaces_stack[-1]
                prev_foldlevel = foldlevel_stack[-1]
                #print("set prev_foldlevel to", prev_foldlevel)
                if DEBUG:
                    print("   <-- decreasing foldlevel to {}".format(prev_foldlevel))

        #
        # Begin setting the foldlevels for various cases.
        #

        if is_empty:
            foldlevel = -5 # The -5 value is later be replaced by the succeeding foldlevel.

        elif line_is_a_continuation:
            foldlevel = prev_foldlevel # Don't separate a line from its continuation.

        else:
            # This part is kind of a finite-state machine handling docstrings after fundef.
            # Otherwise we just set foldlevel to the previous foldlevel.
            begin_fun_or_class_def = is_begin_fun_or_class_def(line, prev_nested,
                                                               in_string, indent_spaces)
            if DEBUG:
                print("   begin_fun_or_class_def:", begin_fun_or_class_def)
                print("   inside_fun_or_class_def:", inside_fun_or_class_def)
                print("   just_after_fun_or_class_def:", just_after_fun_or_class_def)
                print("   inside_docstring:", inside_docstring)
                print("   just_after_fun_docstring:", just_after_fun_docstring)
                print("   foldlevel_stack and indent_spaces_stack:", foldlevel_stack,
                                                                  indent_spaces_stack)

            foldlevel = prev_foldlevel # The fallback value.

            if just_after_fun_docstring:
                # Can occur at the same time as begin_fun_or_class_def: fundef after docstring.
                just_after_fun_docstring = False
                foldlevel = increase_foldlevel(foldlevel_stack, indent_spaces_stack,
                                               new_foldlevel_queue, new_indent_spaces_queue)

            if inside_docstring:
                if not in_string: # Docstring closed at end of line, repeat until.
                    inside_docstring = False
                    just_after_fun_docstring = True

            if just_after_fun_or_class_def:
                just_after_fun_or_class_def = False
                if begins_with_triple_quote:
                    if in_string:
                        inside_docstring = True
                    elif ends_in_triple_quote:
                        # Trigger just_after_fun_docstring, but on next line.
                        just_after_fun_docstring = True
                    else:
                        # Syntax error or single-quote docstring.
                        foldlevel = increase_foldlevel(foldlevel_stack, indent_spaces_stack,
                                                       new_foldlevel_queue, new_indent_spaces_queue)
                else:
                    # Function with no docstring.
                    foldlevel = increase_foldlevel(foldlevel_stack, indent_spaces_stack,
                                                   new_foldlevel_queue, new_indent_spaces_queue)

            if inside_fun_or_class_def:
                if not nested: # or in_string:
                    inside_fun_or_class_def = False
                    just_after_fun_or_class_def = True

            if begin_fun_or_class_def:
                # Note this can be True at same time as either
                # just_after_fun_or_class_def or just_after_fun_docstring (i.e., fundef
                # right after fundef).  Hence the queue of new foldlevel values and indent
                # lines values to set.  The queue which will hold at most two elements.

                if nested or in_string:
                    inside_fun_or_class_def = True
                else:
                    just_after_fun_or_class_def = True

                # New foldlevels, but deferred until after possibly processing off a
                # docstring following the function def.
                new_indent_spaces_queue.insert(0, indent_spaces + shiftwidth)
                new_foldlevel_queue.insert(0, foldlevel_stack[-1] + 1)

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
        line_is_a_continuation = line_has_a_contination

    # Handle the case where foldlevel of last line was set to -5; replace sequence with 0.
    if foldlevel_cache[line_num] == -5:
        replace_preceding_minus_five_foldlevels(foldlevel_cache, line_num, 0)


