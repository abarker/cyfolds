"""

Be sure that annotation typing is turned on, or the compile won't work right.

"""

try:
    from setuptools import setup
    from setuptools import Extension
except ImportError:
    print("The setuptools package is required, try 'pip3 install setuptools "
            "--user' or an equivalent command to install it.")
    import sys; sys.exit(1)
try:
    from Cython.Build import cythonize
except ImportError:
    print("The cython package is required, try 'pip3 install cython --user' "
          "or an equivalent command to install it.")
    import sys; sys.exit(1)


GLOBAL_CYTHON_DIRECTIVES={ # Set as compiler_directives kwarg to cythonize.
        "annotation_typing": True, # Type info from PEP484 annotations, keep True.
        "infer_types": True, # Default is None, keep true.
        #"infer_types.verbose": True,
        "optimize.use_switch": True, # Default is True.
        "optimize.unpack_method_calls": True, # Default is True.
        "language_level": 3,

        #"warn.undeclared": True,
        #"warn.unreachable": True,
        "warn.maybe_uninitialized": True,
        #"warn.unused": True,
        #"warn.unused_arg": True,
        #"warn.unused_result": True,
        }

extensions = [Extension("cyfolds", ["cyfolds.pyx"],
                        extra_compile_args=["-O3"],
                        #extra_compile_args=["-O1"],
                        include_dirs=[],
                        libraries=[],
                        library_dirs=[],
                        )]

ext_modules = cythonize(extensions,
                        compiler_directives=GLOBAL_CYTHON_DIRECTIVES,
                        verbose=True,
                        force=True,
                        annotate=True, # Create the HTML annotation file.
                        )

setup(
    name="cyfolds",
    ext_modules=ext_modules,
    zip_safe=False, # Zipped egg file will not work with cimport for pxd files.
)

