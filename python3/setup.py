"""

Be sure that annotation typing is turned on, or the compile won't work right.

"""

from setuptools import setup
from setuptools import Extension
from Cython.Build import cythonize

GLOBAL_CYTHON_DIRECTIVES={ # Set as compiler_directives kwarg to cythonize.
        "infer_types": True,
        "annotation_typing": True, # Whether to take type info from PEP484 annotations.
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

