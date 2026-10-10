"""Pytest tests for the fold calculations of both the pure-Python `pyfolds` module
and the compiled Cython `cyfolds` module (skipped if it has not been compiled).

Run with `pytest` from the project root or the `test` directory."""
#==============================================================================
# This file is part of the Cyfolds package, Copyright (c) 2019 Allen Barker.
# License details (MIT) can be found in the file LICENSE.
#==============================================================================

import ast
import glob
import importlib
import os
import sys
import textwrap

import pytest

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(TEST_DIR, "..", "python3"))

EXTENDED_KEYWORDS = "class,def,async def,for,while,if,else,try,except,finally"


def import_fold_module(name):
    """Import and return the fold module `name`, or skip the test if it cannot be
    imported.  A missing compiled module can import as an empty namespace package
    (from any directory named `cyfolds`), so the module contents are checked."""
    try:
        module = importlib.import_module(name)
    except ImportError as e:
        pytest.skip("Cannot import {}: {}".format(name, e))
    if not hasattr(module, "get_foldlevels"):
        pytest.skip("Module {} is not compiled for this Python.".format(name))
    return module


@pytest.fixture(params=["pyfolds", "cyfolds"])
def folds(request):
    """Return a function that computes the foldlevels for some code, using each
    fold module in turn."""
    module = import_fold_module(request.param)

    def get_folds(code, shiftwidth=4, lines_of_module_docstrings=-1,
                  lines_of_fun_and_class_docstrings=-1,
                  increase_toplevel_non_class_foldlevels=False,
                  keywords="class,def,async def"):
        """Return the list of foldlevels for the string or line list `code`."""
        if isinstance(code, str):
            code = textwrap.dedent(code).splitlines()
        module.setup_regex_pattern(keywords)
        return module.get_foldlevels(shiftwidth, lines_of_module_docstrings,
                                     lines_of_fun_and_class_docstrings,
                                     increase_toplevel_non_class_foldlevels, code)
    return get_folds


#
# Tests against saved fold data.
#

testdata_files = sorted(glob.glob(os.path.join(TEST_DIR, "*.testdata")))

@pytest.mark.parametrize("data_file", testdata_files, ids=os.path.basename)
def test_saved_testdata(folds, data_file):
    """The computed folds match those saved in the `.testdata` files."""
    with open(data_file) as f:
        expected = [int(line) for line in f]
    with open(data_file[:-len(".testdata")]) as f:
        code_lines = f.read().splitlines()
    assert folds(code_lines) == expected


#
# Regression tests for specific bugs.
#

class MockVimBuffer:
    """A sequence of lines which, like `vim.buffer`, is not a list."""
    def __init__(self, lines):
        self._lines = lines

    def __len__(self):
        return len(self._lines)

    def __getitem__(self, index):
        return self._lines[index]


def test_non_list_buffer(folds):
    """Vim passes a `vim.buffer` rather than a list.  Cython 3 enforces `List`
    annotations as exact list types, which made every call fail in Vim."""
    code = ["def f():", "    return 1", ""]
    assert folds(MockVimBuffer(code)) == folds(code) == [0, 1, 0]


def test_three_space_indent_with_else(folds):
    """With three-space indents and shiftwidth=4 the `else` dedent must not
    end the function fold."""
    code = """\
        def always_on_top(sleeptime, title=None):
           # Sleep for the given time.
           time.sleep(sleeptime)

           if title:
               subprocess.Popen(["wmctrl", "-r", title])
           else:
               subprocess.Popen(["wmctrl", "-r", ":ACTIVE:"])

        x = 1
        """
    assert folds(code) == [0, 1, 1, 1, 1, 1, 1, 1, 0, 0]


def test_three_space_indent_with_docstring(folds):
    """Same as above, but with a docstring."""
    code = """\
        def f(observable):
           \"\"\"Docstring.\"\"\"

           if isinstance(observable, list):
               pass

           return value
        """
    assert folds(code) == [0, 0, 1, 1, 1, 1, 1]


def test_three_space_indent_with_blank_docstring_and_else(folds):
    """Same as above, with a blank docstring followed by comments."""
    code = '''\
        def always_on_top(sleeptime, title=None):
           """ """
           # Sleep for the given time.
           time.sleep(sleeptime)

           # If title is provided, run wmctrl in the background.
           if title:
               subprocess.Popen(["wmctrl", "-r", title])
           else:
               # Otherwise, run wmctrl on the active window.
               subprocess.Popen(["wmctrl", "-r", ":ACTIVE:"])
        '''
    assert folds(code) == [0, 0] + [1] * 9


def test_three_space_indent_after_multiline_argument(folds):
    """A dedent after a parenthesized, multiline string argument must not end
    the fold when the indent is three spaces."""
    code = '''\
        def parse_args():
           parser.add_argument("--fontfile", help=
                   f"""Fontfile name.
                   """)
           parser.add_argument("--fontsize", help=
                   f"""Font size.""")
           return parser.parse_args()
        '''
    assert folds(code) == [0, 1, 1, 1, 1, 1, 1]


def test_three_space_nested_function_has_higher_foldlevel(folds):
    """A nested function must get a higher foldlevel than its enclosing function
    even when the indent is not a multiple of shiftwidth."""
    code = """\
        def outer():
           x = 1
           def inner():
              return x
           return inner
        """
    assert folds(code) == [0, 1, 1, 2, 1]


def test_triple_quote_inside_parens_is_not_docstring(folds):
    """A triple quote starting a line inside parentheses is an argument, not a
    docstring, so module-docstring folding must not add a fold for it."""
    code = '''\
        def parse_command_line():
            """Parse the command-line arguments."""

            parser.add_argument("-l", type=float, help=
                """Approximate latency in starting the video.  Approximate it
                by hitting space when you first see any video and then hitting
                'q'.  Use the leftmost time displayed on the terminal.""")
            return args
        '''
    assert folds(code, lines_of_module_docstrings=2) == [0, 0, 1, 1, 1, 1, 1, 1]


@pytest.mark.parametrize("lines_of_module_docstrings", [0, 1, 2])
def test_triple_quote_inside_parens_does_not_crash(folds, lines_of_module_docstrings):
    """This case used to pop the bottom of the foldlevel stack, raising an
    IndexError, and the following function was then folded incorrectly."""
    code = '''\
        def parse_command_line():
            """Parse the command-line arguments."""
            parser = argparse.ArgumentParser(description=
                    """Interactively generate times for a list of lyrics.
                    To use it you run the program, passing it the video
                    and the lyric file.  The lyric file should have one
                    lyric on each line.""")
            args = parser.parse_args()
            return args

        def main():
            args = parse_command_line()
            print()
        '''
    result = folds(code, lines_of_module_docstrings=lines_of_module_docstrings)
    assert result == [0, 0] + [1] * 7 + [0, 0, 1, 1]


def test_braces_count_as_nesting(folds):
    """A closing brace at column zero inside a function does not end the fold."""
    code = """\
        def f():
            d = {
                1: 2,
        }
            return d
        """
    assert folds(code) == [0, 1, 1, 1, 1]


def test_empty_body_does_not_start_fold(folds):
    """A fold keyword with an empty body (a syntax error) must not start a fold
    on a following, less-indented line."""
    code = """\
        def f():
            if args.preview:

            def no_docstring():
                pass

            x = 1
        """
    assert folds(code, keywords=EXTENDED_KEYWORDS) == [0, 1, 1, 1, 2, 1, 1]


def test_comment_dedented_below_body_ends_fold(folds):
    """A comment dedented below the body indent (but not to the def indent) ends
    the fold, while one at the body indent does not."""
    code = """\
        def f():
            def g():
                x = 1
                # Should fold.
               # Should not fold.
        """
    assert folds(code) == [0, 1, 2, 2, 1]


def test_empty_buffer(folds):
    """An empty buffer gives an empty list rather than raising an IndexError."""
    assert folds([]) == []


def test_increase_toplevel_non_class_foldlevels(folds):
    """The option puts toplevel function bodies at the same foldlevel as method
    bodies.  Methods used to get the extra level too, because the flag for being
    inside a toplevel class was always reset on the line after the class line."""
    code = '''\
        def f():
            return 1

        class A:
            """Doc."""

            def m(self):
                pass

        class B:
            x = 1
            def m(self):
                pass

        def g():
            return 2
        '''
    assert folds(code, increase_toplevel_non_class_foldlevels=True) == [
            0, 2, 0, 0, 0, 1, 1, 2, 0, 0, 1, 1, 2, 0, 0, 2]
    assert folds(code) == [0, 1, 0, 0, 0, 1, 1, 2, 0, 0, 1, 1, 2, 0, 0, 1]


#
# Tests of the docstring settings.
#

FUN_DOCSTRING_CODE = '''\
    def f():
        """Line one.
        Line two.
        Line three.
        """
        return 1
    '''

@pytest.mark.parametrize("lines_of_docstrings, expected", [
        (-1, [0, 0, 0, 0, 0, 1]), # Keep the full docstring unfolded.
        (0, [0, 1, 1, 1, 1, 1]),
        (1, [0, 0, 1, 1, 1, 1]),
        (2, [0, 0, 0, 1, 1, 1]),
        ])
def test_lines_of_fun_and_class_docstrings(folds, lines_of_docstrings, expected):
    """The given number of function docstring lines is left unfolded."""
    assert folds(FUN_DOCSTRING_CODE,
                 lines_of_fun_and_class_docstrings=lines_of_docstrings) == expected


MODULE_DOCSTRING_CODE = '''\
    """Module line one.
    Line two.
    Line three.
    Line four.
    """
    x = 1
    '''

@pytest.mark.parametrize("lines_of_docstrings, expected", [
        (-1, [0, 0, 0, 0, 0, 0]), # Keep the full docstring unfolded.
        (2, [0, 0, 2, 2, 0, 0]), # The last line is never folded.
        ])
def test_lines_of_module_docstrings(folds, lines_of_docstrings, expected):
    """The given number of module docstring lines is left unfolded."""
    assert folds(MODULE_DOCSTRING_CODE,
                 lines_of_module_docstrings=lines_of_docstrings) == expected


#
# Tests of various syntax.
#

def test_decorator_and_async_def(folds):
    """Decorators are not folded, and `async def` starts a fold."""
    code = """\
        @decorator
        async def f():
            await g()
        """
    assert folds(code) == [0, 0, 1]


def test_custom_fold_keywords(folds):
    """Cython keywords can be added to the fold keywords."""
    code = """\
        cdef int f(int x):
            return x
        cpdef g():
            pass
        """
    assert folds(code, keywords="class,def,async def,cdef,cpdef") == [0, 1, 0, 1]
    assert folds(code) == [0, 0, 0, 0]


def test_no_fold_without_body_on_next_line(folds):
    """Names starting with keywords and single-line definitions are not folded."""
    code = """\
        class_name = 1
        define = 2
        def f(): return 1
        x = 3
        """
    assert folds(code) == [0, 0, 0, 0]


def test_multiline_definitions(folds):
    """Parameter lists continued with brackets or backslashes stay unfolded."""
    code = """\
        def f(a,
              b):
            return 1
        def g(a, \\
              b):
            return 2
        """
    assert folds(code) == [0, 0, 1, 0, 0, 1]


def test_syntax_inside_strings_is_ignored(folds):
    """Keywords, comment characters, quotes, and brackets inside strings are
    ignored."""
    code = """\
        def f():
            s = "def g(): # not code"
            t = 'it\\'s ( [ {'
            return s
        x = 1
        """
    assert folds(code) == [0, 1, 1, 1, 0]


def test_docstring_detection_matches_python(folds):
    """A docstring after empty lines is still a docstring, as in Python, while
    f-strings and b-strings are not docstrings."""
    code = '''\
        def f():

            """Docstring."""
            x = 1
        def g():
            f"""Not a docstring."""
            x = 1
        def h():
            b"""Not a docstring."""
            x = 1
        '''
    assert folds(code) == [0, 0, 0, 1, 0, 1, 1, 0, 1, 1]


# Each case is the body of a function, starting with what might be a docstring.
DOCSTRING_CASES = [
    ['"""Doc."""'], ['"Doc."'], ["'Doc.'"], ["''"], ['"Doc " "string."'],
    ['"""a""" """b"""'], ['"a" r"b"'], ['u"""Doc."""'], ['R"""Doc."""'], ['U"Doc."'],
    [r'r"Doc \d."'], ['"""Doc."""  # Comment.'], ['"Doc."  # Comment.'],
    [r'"a \"quoted\" doc."'], [r"'it\'s doc.'"], ['"""Doc', 'more."""'],
    ['"a" + "b"'], ['"""a""" + """b"""'], ['"""Doc""".format(x)'], ['"""Doc""" % x'],
    ['"Doc", 1'], ['"Doc"[0]'], ['"Doc".strip()'], ['"Doc" "x".join(y)'],
    ['"a" f"b"'], ['f"Not doc."'], ['b"Not doc."'], ['rb"Not doc."'], ['Rb"Not doc."'],
    ['r = 1'], ['u.x = 1'], ['rx = "a"'],
    ]

# Cases where the folds do not match Python, known limitations.
DOCSTRING_CASES += [pytest.param(body, marks=pytest.mark.xfail(reason=reason, strict=True))
                    for body, reason in [
    (['"""Doc.""";  x = 1'], "Statements after a semicolon are not handled."),
    (['"""Doc', 'more.""".strip()'], "The fold is set before the operator is seen."),
    (['("Doc "', ' "string.")'], "Multi-line concatenation is not handled."),
    (['"Doc " \\', '"string."'], "Multi-line concatenation is not handled."),
    ]]

@pytest.mark.parametrize("body", DOCSTRING_CASES,
                         ids=lambda body: " / ".join(body))
def test_docstrings_match_python(folds, body):
    """A function's first statement is left unfolded exactly when Python treats
    it as a docstring."""
    lines = ["def f():"] + ["    " + line for line in body] + ["    x = 1"]
    function = ast.parse("\n".join(lines)).body[0]
    is_docstring = ast.get_docstring(function) is not None
    result = folds(lines)
    is_unfolded = all(level == 0 for level in result[1:1 + len(body)])
    assert is_unfolded == is_docstring


def test_one_line_docstrings_with_settings(folds):
    """One-line docstrings of any quote style follow the docstring settings."""
    code = """\
        def f():
            'Doc.'
            x = 1
        def g():
            "Doc " "string."
            x = 1
        """
    assert folds(code) == [0, 0, 1, 0, 0, 1]
    assert folds(code, lines_of_fun_and_class_docstrings=0) == [0, 1, 1, 0, 1, 1]


def test_tab_indents(folds):
    """Tab indents are handled."""
    code = "def f():\n\tif x:\n\t\treturn 1\n\treturn 2\ny = 1"
    assert folds(code.splitlines()) == [0, 1, 1, 1, 0]


@pytest.mark.parametrize("shiftwidth", [4, 8])
def test_tab_indents_with_nested_blocks(folds, shiftwidth):
    """Tab-indented functions with blank lines and nested blocks fold fully."""
    code = ("def main():\n"
            "\n"
            "\toption = ''\n"
            "\tfor i in range(1, lth - 1) :\n"
            "\t\tif (sys.argv[i] == '-f') :\n"
            "\t\t\toption = sys.argv[i]\n"
            "\t\telif (sys.argv[i] == '-h') :\n"
            "\t\t\thtml = ' --html '\n"
            "\n"
            "\tif (option == ''):\n"
            "\t\toption = '-f'\n"
            "\n"
            "x = 1")
    assert folds(code.splitlines(), shiftwidth=shiftwidth) == [0] + [1] * 10 + [0, 0]


#
# Tests over all the code files with many combinations of settings.
#

# The large file is left out to keep these tests fast; it is still checked with
# the default settings by `test_saved_testdata`.
code_files = [f[:-len(".testdata")] for f in testdata_files
              if "large_file" not in f] + [
        os.path.join(TEST_DIR, "example_foldlevels.py"),
        os.path.join(TEST_DIR, "..", "python3", "pyfolds.py"),
        os.path.join(TEST_DIR, "..", "python3", "cyfolds.pyx")]

setting_combinations = [(keywords, shiftwidth, module_docstrings, fun_docstrings, increase)
                        for keywords in ["class,def,async def", EXTENDED_KEYWORDS]
                        for shiftwidth in [2, 3, 4]
                        for module_docstrings in [-1, 0, 2]
                        for fun_docstrings in [-1, 0, 2]
                        for increase in [False, True]]

def read_code_lines(code_file):
    """Return the list of lines in the file `code_file`."""
    with open(code_file) as f:
        return f.read().splitlines()


@pytest.mark.parametrize("code_file", code_files, ids=os.path.basename)
def test_valid_foldlevels_for_all_settings(folds, code_file):
    """Every setting combination gives a valid foldlevel for every line, without
    raising an exception."""
    code_lines = read_code_lines(code_file)
    for keywords, shiftwidth, module_docstrings, fun_docstrings, increase in (
            setting_combinations):
        result = folds(code_lines, shiftwidth, module_docstrings, fun_docstrings,
                       increase, keywords)
        assert len(result) == len(code_lines)
        assert all(level >= 0 for level in result)


@pytest.mark.parametrize("code_file", code_files, ids=os.path.basename)
def test_cython_and_python_versions_agree(code_file):
    """The compiled Cython module and the pure-Python module give identical folds
    for every setting combination, so the two versions are kept in sync."""
    pyfolds = import_fold_module("pyfolds")
    cyfolds = import_fold_module("cyfolds")
    code_lines = read_code_lines(code_file)
    for keywords, shiftwidth, module_docstrings, fun_docstrings, increase in (
            setting_combinations):
        results = []
        for module in (pyfolds, cyfolds):
            module.setup_regex_pattern(keywords)
            results.append(module.get_foldlevels(shiftwidth, module_docstrings,
                                                 fun_docstrings, increase, code_lines))
        assert results[0] == results[1], (keywords, shiftwidth, module_docstrings,
                                          fun_docstrings, increase)
