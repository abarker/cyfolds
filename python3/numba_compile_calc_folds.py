"""


"""

from numba.pycc import CC

cc = CC("calc_folds")
# Uncomment the following line to print out the compilation steps
cc.verbose = True

@cc.export("calc_foldlevels", 'int64(int64[:], unichr[:])')

# Todo: read this into file, and put above decorator on calc_foldlevels.

@cc.export('multi', 'i4(i4, i4)')
def mult(a, b):
    return a * b

@cc.export('square', 'f8(f8)')

def square(a):
    return a ** 2

if __name__ == "__main__":
    cc.compile()


