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
        "infer_types": True,
        "optimize.use_switch": True,
        "optimize.unpack_method_calls": True,
        "language_level": 3,
        }

extensions = [Extension("cyfolds", ["cyfolds.pyx"],
                        #extra_compile_args=["-O1"],
                        extra_compile_args=["-O3"],
                        include_dirs=[],
                        libraries=[],
                        library_dirs=[],
                        )]

ext_modules = cythonize(extensions,
                        compiler_directives=GLOBAL_CYTHON_DIRECTIVES,
                        verbose=True,
                        force=True,
                        )

setup(
    name="cyfolds",
    ext_modules=ext_modules,
    zip_safe=False, # Zipped egg file will not work with cimport for pxd files.
)

