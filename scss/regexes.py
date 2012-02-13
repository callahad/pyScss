# -*- coding: utf-8 -*-

import re

from .colors import _colors, _reverse_colors
from .units import _zero_units


SEPARATOR = '\x00'
_nl_re = re.compile(r'\s*\n\s*', re.MULTILINE)
_nl_num_re = re.compile(r'\n.+' + SEPARATOR, re.MULTILINE)
_nl_num_nl_re = re.compile(r'\n.+' + SEPARATOR + r'\s*\n', re.MULTILINE)

_reverse_colors_re = re.compile(r'(?<![-\w.#$])(' + '|'.join(map(re.escape, _reverse_colors)) + r')(?![-\w])', re.IGNORECASE)
_colors_re = re.compile(r'(?<![-\w.#$])(' + '|'.join(map(re.escape, _colors)) + r')(?![-\w])', re.IGNORECASE)

_expr_glob_re = re.compile(r'''
    \#\{(.*?)\}                   # Global Interpolation only
''', re.VERBOSE)

_ml_comment_re = re.compile(r'\/\*(.*?)\*\/', re.DOTALL)
_sl_comment_re = re.compile(r'(?<!\w{2}:)\/\/.*')
_zero_units_re = re.compile(r'\b0(' + '|'.join(map(re.escape, _zero_units)) + r')(?!\w)', re.IGNORECASE)
_zero_re = re.compile(r'\b0\.(?=\d)')

_escape_chars_re = re.compile(r'([^-a-zA-Z0-9_])')
_variable_re = re.compile('^\\$[-a-zA-Z0-9_]+$')
_interpolate_re = re.compile(r'(#\{\s*)?(\$[-\w]+)(?(1)\s*\})')
_spaces_re = re.compile(r'\s+')
_expand_rules_space_re = re.compile(r'\s*{')
_collapse_properties_space_re = re.compile(r'([:#])\s*{')

_strings_re = re.compile(r'([\'"]).*?\1')
_blocks_re = re.compile(r'[{},;()\'"\n]')

_prop_split_re = re.compile(r'[:=]')
_skip_word_re = re.compile(r'-?[_\w\s#.,:%]*$|[-_\w#.,:%]*$', re.MULTILINE)
_has_code_re = re.compile('''
    (?:^|(?<=[{;}]))            # the character just before it should be a '{', a ';' or a '}'
    \s*                         # ...followed by any number of spaces
    (?:
        (?:
            \+
        |
            @include
        |
            @warn
        |
            @mixin
        |
            @function
        |
            @if
        |
            @else
        |
            @for
        |
            @each
        )
        (?![^(:;}]*['"])
    |
        @import
    )
''', re.VERBOSE)

FUNCTIONS_CSS2 = 'attr counter counters url rgb rect'
## CSS3
FUNCTIONS_UNITS = 'calc min max cycle' # http://www.w3.org/TR/css3-values/
FUNCTIONS_COLORS = 'rgba hsl hsla' # http://www.w3.org/TR/css3-color/
FUNCTIONS_FONTS = 'local format' # http://www.w3.org/TR/css3-fonts/
# http://www.w3.org/TR/css3-images
FUNCTIONS_IMAGES = 'image element linear-gradient radial-gradient '\
                   'repeating-linear-gradient repeating-radial-gradient'
# http://www.w3.org/TR/css3-2d-transforms/
FUNCTIONS_2D = 'matrix translate translateX translateY scale '\
               'scaleX scaleY rotate skewX skewY'
# http://www.w3.org/TR/css3-3d-transforms/
FUNCTIONS_3D = 'matrix3d translate3d translateZ scale3d scaleZ rotate3d '\
               'rotateX rotateY rotateZ perspective'
# http://www.w3.org/TR/css3-transitions/
FUNCTIONS_TRANSITIONS = 'cubic-bezier'
# http://www.w3.org/TR/css3-animations/
FUNCTIONS_ANIMATIONS = '' # has 'from' and 'to' block selectors, but no new function

VENDORS = '-[^-]+-.+'

_css_functions_re = re.compile(r'^(%s)$' % (
    '|'.join(' '.join([
        FUNCTIONS_CSS2,
        FUNCTIONS_UNITS,
        FUNCTIONS_COLORS,
        FUNCTIONS_FONTS,
        FUNCTIONS_IMAGES,
        FUNCTIONS_2D,
        FUNCTIONS_3D,
        FUNCTIONS_TRANSITIONS,
        FUNCTIONS_ANIMATIONS,
        VENDORS
    ]).split())))
