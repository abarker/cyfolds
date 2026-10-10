"""

This is mostly for testing increasing foldlevel for toplevel non-class elements.

"""

class Outer:
    """Module level"""
    def __init__(self):
        """Method of module-level class."""
        pass

    class Inner:
        """Nested class in module-level class."""

        def __init__(self):
            """Method of class nested in class."""
            pass

    x = 4

try:
    class Outer:
        class Inner:
            def __init__(self):
                pass
        x = 4
except:
    pass

def module_scope_fun():
    """Module scope function."""
    def nested_fun():
        "Nested fun."
        pass

try:
    def outer_fun():
        """Fun inside module-level try."""
        pass
except:
    pass

class Outer2:
    """Another, to make sure the indicator for inside toplevel classes is switching
    on and off as it should."""

    def __init__(self):
        pass

    class Inner:

        def __init__(self):
            pass


    x = 4

class Outer3:

    def __init__(self):
        pass

    class Inner:

        def __init__(self):
            pass


    x = 4

try:
    class Outer3:
        class Inner:
            def __init__(self):
                pass
        x = 4
except:
    pass

def another_outer_level_fun():

    pass

