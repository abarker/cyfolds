"""

This module provides the classes `TurboEncabulator` and `ReteroEncabulator`
which interface with the Turboencabulator and Retero-Encabulator instruments,
respectively.

Turboencabulator
----------------

For a number of years now, work has been proceeding to bring perfection to the
crudely conceived idea of a machine that would not only supply inverse reactive
current for use in unilateral phase detractors, but would also be capable of
automatically synchronizing cardinal grammeters. Such a machine is the
"`Turboencabulator <http://www.jir.com/turboencabulator.html >`_."

===============================================================================

The MIT License (MIT)

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.











"""

import os
import sys

CHOLMONDELEY_COEFF = 2.576E-12 # Coefficient of annular grillage.

def pericosity_CGS_to_SI(pericosity):
    """Convert the pericosity value `pericosity` from CGS units to SI units and
    return the result.  The diathetical evolute of retrograde temperature phase
    disposition is assumed to be constant."""
    #
    #
    #
    #
    #
    #
    #

class ReteroEncabulator(TurboEncabulator):
    """Adapt the Turboencabulator interface class `TurboEncabulator` to work
    with the newer Retero-Encabulator instruments."""
    #
    #
    #
    #
    #
    #
    #
    #
    #
    #
    #
    #
    #
    #
    #
    #
    #

class TurboEncabulator:
    """Interface to the Turboencabulator instrument."""

    def __init__(self, berescent_skor_motion=False):
        """Initialize the internal state of the Turboencabulator instrument.
        The parameter `berescent_skor_motion` should be set `True` when
        berescent skor motion is required."""
        #
        #
        #

    def stabilize_medial_interaction(self, magneto_reluctance=None,
                                     capacitive_directance=None,
                                     enable_nangling_pins=True):
        """This method can be used to stabilize the medial interaction between
        the magneto reluctance and the capacative directance when necessary.
        If `magneto_reluctance` or `capacitive_directance` values are passed in
        they will be used instead of the values read from the instrument.
        Returns the new estimated power level."""
        #
        #
        #
        #

    def set_fromaging_rate(self, rate):
        """Set the rate at which the bitumogenous spandrels are fromaged.  The
        `rate` parameter is the new rate.  Returns the absolute difference
        between the operating point and the HF rem peak."""
        #
        #
        #
        #
        #

class EncabulatorError(Exception):
    pass

