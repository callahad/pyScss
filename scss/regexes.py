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
_skip_word_re = re.compile(r'-?[\w\s#.,:%]*$|[\w\-#.,:%]*$', re.MULTILINE)
_skip_re = re.compile(r'''
    (?:url|alpha)\([^)]*\)$
|
    [\w\-#.,:%]+(?:\s+[\w\-#.,:%]+)*$
''', re.MULTILINE | re.IGNORECASE | re.VERBOSE)
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

_css_function_re = re.compile(r'^(from|to|mask|rotate|format|local|url|attr|counter|counters|color-stop|rect|-webkit-.*|-webkit-.*|-moz-.*|-pie-.*|-ms-.*|-o-.*)$')
