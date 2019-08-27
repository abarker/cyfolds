"""

vim.current.buffer is the current buffer, list-like.
It is modifiable.

NOTE: Lines number from zero in Python object!!!!!

Because this in this style the foldlevel of any line is the same as the foldlevel
of the line before it, updates can be fast in some circumstances.

Changes on line x do not need to modify anything before x, and changes after x
are propagated until the new level agrees with the old one.  (Of course there
are a couple of exceptions to be handled, and changes in strings need to be handled,
etc...)

Comments always start with # which can be checked, but can end with triple quote;
would need to make sure not a comment line.

Strings only matter just after a fun or class def, which greatly simplifies processing.
But we do need to make sure that the "def" or "class" is not inside a multi-line string,
like quoted-out code.  Escapes in strings for quotes need to be handled.

How to handle lines added or removed???  Is it possible to detect where that happened?
How efficient is checking for changes on lines?

--> Really just need to go through and identify all the fun or class defs (not in strings)
    and then the closing line, after the docstring if there is one.  Just need the logic
    to turn on and off the "in_string" flags.  All the folding levels can be done in
    one pass like that.  Maybe get that working, then consider optimize.

The vim python API docs (same as ':help python').
   https://docs.huihoo.com/vim/7.2/if_pyth.htm

Premature, but what if you 1) wrote the buffer out to a Python virtual file (file object
good to pass to vim command? 2) In numba you read the lines back in and then process
them.  Saves having to have a Python loop to do the conversion to ordinary list.
Is converting to ordinary list and using numba really worth it, or is the copy going
to undo any good?


--> What if you saved sequential forward hashes for each line, and sequential backward
hashes for each line.  Then you could find the beginning and ending pieces that were
unchanged for a given middle spot to evaluate... just copy over and fill in...

--> Could you just save a copy instead and to through from the first to find the
    point where they differ (or go back from the point passed in???).  Then, just
    compute forward until the lines and indents match... rest must match under some
    weak conditions...

--> May be just as efficient or more to just start from beginning of file each time,
    comparing strings rather that computing (but is that faster than recomputing,
    where we can skip a lot?)  If you use hash chain you still need to goto the end
    of the file computing the updates.

"""

testing = False
try:
    import vim
except ImportError: # Testing.
    testing = True
    class Current:
        buffer = []
    class vim:
        current = Current

from collections import namedtuple
from typing import List, Tuple, Set
import re
import numpy as np

print("before numba")
import numba # test speed, import a bit slow... might want on-demand folding, not auto...
from numba import njit
print("after numba")

DEBUG = False


LineData = namedtuple('LineData', ["foldlevel",])
                                   #"indent_level",
                                   #"begin_fun_or_class_def",
                                   #"is_in_string",
                                   #"is_in_comment",
                                   #"is_end_of_docstring"])

prev_buffer_hash = 0
prev_foldlevel_cache = None # Previous buffer data, set to numpy array of int.
recalcs = 0

FUN_OR_CLASS = ("def ", "class ", "async def ")

patt = "aa(b)*[1-9]"
re.search(patt, "ZZZaab9QQQ") # search finds matches anywhere in string
re.match(patt, "aab9ZZZZZ") # match starts at beginning

bracket_chars = set(["(", ")", "[", "]", "{", "}"])
paren_and_escape_chars = set(["'", '"', "\\"])
whitespace = set([" ", "\t"])

#buffer_data = [process_line(count, line) for count, line in enumerate(vim.current.buffer)]

#def indent_level(lnum):
#    lnum -= 1
#    line = vim.current.buffer[lnum]
#    return (len(line) - len(line.lstrip())) // 4
#    #current_indent = vim.eval("indent({})".format(int(lnum)))
#    #return int(current_indent) // 4 # Hardcoded 4 for now........
#
#def is_empty(lnum):
#    lnum -= 1
#    line = vim.current.buffer[lnum]
#    return line.strip() == ""
#
#def fun_or_class_def(lnum):
#    lnum -= 1
#    return any(vim.current.buffer[lnum].startswith(s) for s in FUN_OR_CLASS) # Use regex.

def foldlevel(lnum, foldnestmax):
    """Recalculate all the line data for lines `lnum` and greater."""
    # Convert to a list of strings.
    global prev_foldlevel_cache, prev_buffer_hash
    lnum = int(lnum) - 1 # Compensate for different numbering convention.
    if not testing:
        buffer_data = vim.current.buffer
    else:
        buffer_data = lines
    buffer_data = [i for i in buffer_data]
    assert buffer_data

    buffer_hash = hash(tuple(buffer_data))
    #print("hash and prev hash", buffer_hash, prev_buffer_hash)
    dirty_cache = buffer_hash != prev_buffer_hash
    prev_buffer_hash = buffer_hash
    #dirty_cache = True
    if dirty_cache:
        prev_foldlevel_cache = np.empty((len(buffer_data),), dtype=int)
        calculate_foldlevels(prev_foldlevel_cache, buffer_data)
        global recalcs
        recalcs += 1
        #print("recalcs", recalcs, "saved folds", prev_foldlevel_cache)

    foldlevel = prev_foldlevel_cache[lnum]
    return foldlevel

@njit(cache=True, parallel=True, nogil=True)
def calculate_foldlevels(prev_foldlevel_cache, buffer_data: Tuple[str]) -> int:
    """Do the actual calculations and return the foldlevel."""
    in_single_quote_string = False
    in_double_quote_string = False
    in_single_quote_docstring = False
    in_double_quote_docstring = False

    def is_in_string():
        return (in_single_quote_string or in_single_quote_docstring or
                in_double_quote_string or in_double_quote_docstring)

    nest_parens = 0
    nest_brackets = 0
    nest_braces = 0

    def is_nested():
        return nest_parens or nest_brackets or nest_braces

    inside_fun_or_class_def = False
    just_after_fun_or_class_def = False
    inside_docstring = False
    ended_fun_docstring = False

    foldlevel = 0
    prev_foldlevel = 0
    nested = False
    prev_nested = False
    indent_level = 0
    prev_indent_level = 0
    in_string = False
    prev_in_string = False

    foldlevel_stack = [] # Stack of foldlevels with each increase.
    indent_level_stack = [] # Corresponding stack of indent levels.

    for line_num, line in enumerate(buffer_data):
        print(line_num)
        line = line.rstrip() # Makes finding end of docstring easier.
        ends_in_triple_quote = False
        begins_with_triple_quote = False
        first_nonwhitespace = False
        indent_level = None
        is_comment = False
        is_empty = False
        escaped_char = False

        line_len = len(line)
        if line == "": # Was rstripped.
            assert line_len == 0
            indent_level = 0
            is_empty = True
            is_comment = False

        # Loop over char in the line.
        i = -1
        while not is_empty:
            i += 1
            if i >= line_len:
                break

            in_string = is_in_string()
            nested = is_nested()
            char = line[i]
            if indent_level is None and char != " " and char != "\t": #not in whitespace:
                indent_level = i

            # Comments.
            if not in_string and char == "#":
                is_comment = True
                foldlevel = prev_foldlevel
                break # Comments make no difference.

            # Escape char.
            if in_string and char == "\\":
                escaped_char = True
                continue
            tmp_escaped_char = escaped_char
            escaped_char = False

            # Strings.
            if char == '"' and not tmp_escaped_char:
                if i + 2 < line_len and line[i+1] == '"' and line[i+2] == '"':
                    if in_double_quote_docstring or not in_string:
                        if in_string and i == line_len - 3:
                            ends_in_triple_quote = True
                        elif not in_string and i == indent_level:
                            begins_with_triple_quote = True
                        in_double_quote_docstring = not in_double_quote_docstring
                    i += 2
                elif in_double_quote_string or not in_string:
                    in_double_quote_string = not in_double_quote_string
                continue
            if char == "'" and not tmp_escaped_char:
                if i + 2 < line_len and line[i+1] == "'" and line[i+2] == "'":
                    if in_single_quote_docstring or not in_string:
                        if in_string and i == line_len - 3:
                            ends_in_triple_quote = True
                        elif not in_string and i == indent_level:
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

        in_string = is_in_string()
        nested = is_nested()
        # TODO stuff after nested fun/class defs is not being reset to prev indent level
        """
        if line_num == lnum:

            if DEBUG:
                print(
                "\n   inside_fun_or_class_def",
                inside_fun_or_class_def,
                "\n   just_after_fun_or_class_def",
                just_after_fun_or_class_def,
                "\n   inside_docstring",
                inside_docstring,
                "\n   ended_fun_docstring",
                ended_fun_docstring,
                "\n   nested",
                nested,
                "\n   in_string",
                in_string,
                )
        """

        dedent = not prev_in_string and not prev_nested and (prev_indent_level > indent_level)
        if False: #dedent: TODO work this stuff out or delete it.....
            while len(indent_level_stack) >= 1 and indent_level < indent_level_stack[-1]:
                ind = indent_level.pop()
                fld = foldlevel_stack.pop()
            foldlevel = indent_level // 4

        elif is_empty:
            foldlevel = prev_foldlevel

        else:
            # TODO: need regex for below; in particular "async def" depends on single space.
            begin_fun_or_class_def = (not prev_nested and not in_string
                                   and (line[indent_level:indent_level+4] == "def "
                                    or  line[indent_level:indent_level+6] == "class "
                                    or  line[indent_level:indent_level+10] == "async def "))

            if begin_fun_or_class_def:
                if nested or in_string:
                    inside_fun_or_class_def = True
                else:
                    just_after_fun_or_class_def = True
                foldlevel = indent_level // 4 # Hardcoded 4...................

            elif inside_fun_or_class_def:
                if not nested or in_string:
                    inside_fun_or_class_def = False
                    just_after_fun_or_class_def = True

            elif just_after_fun_or_class_def:
                just_after_fun_or_class_def = False
                if begins_with_triple_quote:
                    if in_string:
                        inside_docstring = True
                    elif ends_in_triple_quote:
                        ended_fun_docstring = True
                    else:
                        # Syntax error or single-quote docstring.
                        foldlevel = prev_foldlevel + 1
                else:
                    # Function with no docstring.
                    foldlevel = prev_foldlevel + 1

            elif inside_docstring:
                if not in_string:
                    inside_docstring = False
                    ended_fun_docstring = True

            elif ended_fun_docstring:
                ended_fun_docstring = False
                foldlevel = prev_foldlevel + 1


        """
        if line_num == lnum:

            if DEBUG:
                print(
                "\n   inside_fun_or_class_def",
                inside_fun_or_class_def,
                "\n   just_after_fun_or_class_def",
                just_after_fun_or_class_def,
                "\n   inside_docstring",
                inside_docstring,
                "\n   ended_fun_docstring",
                ended_fun_docstring,
                "\n   nested",
                nested,
                "\n   in_string",
                in_string,
                )
        """
        prev_foldlevel_cache[line_num] = foldlevel

        # Final var updates for properties across lines, to setup for next line.
        prev_foldlevel = foldlevel
        prev_nested = nested
        prev_in_string = in_string
        prev_indent_level = indent_level

    return indent_level # Something went wrong...

def recursive_foldlevel(lnum: int, foldnestmax: int) -> int:
    """Saved just to consider recursive way..."""
    if lnum == 0:
        return 0

    if fun_or_class_def(lnum):
        #assert vim.current.buffer[lnum][0] == "d" or vim.current.buffer[lnum][0] == "c"
        #assert indent_level(lnum) == 0
        return indent_level(lnum)
    elif fun_or_class_def(lnum - 1):
        return min(indent_level(lnum - 1) + 1, int(foldnestmax))
    elif is_empty(lnum) and fun_or_class_def(lnum + 1):
        return indent_level(lnum + 1)
    else:
        return foldlevel(lnum - 1, foldnestmax)


if __name__ == "__main__":
    testing = True

    test_string = r'''
def egg():
    """Docstring."""
        for i in range(len):
        i = "egg"
        j = 'egg'
        k = "'egg'"
    hello = (a,
             b)

class e(
     object):
    x = "xxx
         yy"
'''
    print()
    lines = test_string.splitlines()
    for i in range(0,14): # Note this fun is based on zero, not like higher-level one.
        print("\nline = '", lines[i], "'", sep="", end="")
        print("foldlevel:", foldlevel(i, 3))

