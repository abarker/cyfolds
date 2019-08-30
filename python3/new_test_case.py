
def handle_options_on_cropped_file(
        input_doc_fname,
        output_doc_fname):
    """Handle the options which apply after the file is written such as previewing
    and renaming."""

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

def main_crop(
        ):
    """Process command-line arguments, do the PDF processing, and then perform
    final processing on the filenames."""

    parsed_args = parse_command_line_arguments(cmd_parser)

    def egg():
        parsed_args
        pass # single line doesn't fold...

    def egg_single_line():
        pass

    # Process some of the command-line arguments (also sets
    # args globally).
    input_doc_fname, fixed_input_doc_fname, output_doc_fname = (
        process_command_line_arguments(parsed_args))

    x = 4
    y = 4


def x():
    def y():
        def z():
            "This one doesn't fold right, but apparently a vim bug because the
            raw foldlevel numbers look correct.  Also fails with docstring after
            y and some code after y and before z"
            x = 4
            y = 5

def a():
    pass
def b():
    pass

with open("egg") as f:
    def fun_in_with():
        x = 5
        y = 5

    egg = 5

    def another_in_with():
        """Docstring."""
        z = 6
        w = 8

x = \
        5
def \
        continued(): \
        \
    """Docstring \"   """
    x += 4

