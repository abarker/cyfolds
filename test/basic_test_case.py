"""1)
2)
3) Module docstring.
4)
5)
"""

def handle_options_on_cropped_file(
        input_doc_fname,
        output_doc_fname):
    """Handle the 'options "which" apply' "after" the file is written such
    as previewing and renaming."""

    def do_preview(output_doc_fname):
        """ """
        viewer = args.preview
        if args.verbose:
            return

    # Handle the '--queryModifyOriginal' option.
    if args.queryModifyOriginal:
        if args.preview:
            print(
                "\nRunning the preview viewer on the file, will query whether or not"
                "\nto modify the original file after the viewer is launched in the"
                "\nbackground...\n")

while var == value:
    print("While loop.")
    print("Two lines.")

    def inside_while_def():
        pass

def main_crop(
        ):
    """1) Process command-line arguments, do the PDF processing, and then perform
    2) final processing on the filenames.
    3)
    4) Longer docstring.
    5)
    6)
    """

    parsed_args = parse_command_line_arguments(cmd_parser)

    def egg():
        parsed_args
        pass

    def egg_single_line():
        pass

    # Process some of the command-line arguments (also sets
    # args globally).
    input_doc_fname, fixed_input_doc_fname, output_doc_fname = (
        process_command_line_arguments(parsed_args))

    x = 4
    y = 4


def x():
    def y(): # Nested one level.
        def z():
            """Triple nest

            """
            x = 4
            y = 5

def a():
    pass
def b():
    pass
def c(): # This fun has comment on its line and only docstring.
    """pass"""

def indented_docstring_end():
    """This docstring ends
       indented, but logically it is not.
                 """
    pass

with open("egg") as f:
    def fun_in_with():
        x = 5
        y = 5

    egg = "'"; zed = """ "." """

    def another_in_with():
        """Docstring."""
        z = 6
        w = 8

        # should fold
        #  should fold
       # should not fold

x = \
        list((5,))

if x == 5: return 66
y = 6; x = (
    4 + 4)

# This one fails because colon at end of line is checked and found missing.
def \
        continued(): \
        \
    """Fake docstring \"   """
    x += 4

def \
        continued(): \

    """Real docstring \"   """
    x += 4

def fun_with_continuation_args(
        a1, \
        a2=2, \
        ): # These would be nested if not continued.
    pass

