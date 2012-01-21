# -*- coding: utf-8 -*-

import logging
import os

from .scss_meta import (BUILD_INFO, PROJECT, VERSION, REVISION, URL, AUTHOR,
                        AUTHOR_EMAIL, LICENSE)


# Variables read by submodules, but never modified.
PROJECT_ROOT = os.path.normpath(os.path.dirname(os.path.abspath(__file__)))
STATIC_URL = '/static/'
ASSETS_URL = '/static/assets/'

# Variables modified by the .cli or .scss submodules.
_cfg = {'LOAD_PATHS': os.path.join(PROJECT_ROOT, 'sass/frameworks/'),
        'STATIC_ROOT': os.path.join(PROJECT_ROOT, 'static/'),
        'ASSETS_ROOT': os.path.join(PROJECT_ROOT, 'static/assets/'),
        'DEBUG': 0,
        'VERBOSITY': 1}


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

_default_scss_files = {}  # Files to be compiled ({file: content, ...})

_default_scss_index = {0: '<unknown>:0'}

_default_scss_vars = {
    '$BUILD_INFO': BUILD_INFO,
    '$PROJECT': PROJECT,
    '$VERSION': VERSION,
    '$REVISION': REVISION,
    '$URL': URL,
    '$AUTHOR': AUTHOR,
    '$AUTHOR_EMAIL': AUTHOR_EMAIL,
    '$LICENSE': LICENSE,

    # unsafe chars will be hidden as vars
    '$__doubleslash': '//',
    '$__bigcopen': '/*',
    '$__bigcclose': '*/',
    '$__doubledot': ':',
    '$__semicolon': ';',
    '$__curlybracketopen': '{',
    '$__curlybracketclosed': '}',

    # shortcuts (it's "a hidden feature" for now)
    'bg:': 'background:',
    'bgc:': 'background-color:',
}

_default_scss_opts = {
    'verbosity': _cfg['VERBOSITY'],
    'compress': 1,
    'compress_short_colors': 1,  # Converts things like #RRGGBB to #RGB
    'compress_reverse_colors': 1,  # Gets the shortest name of all for colors
    'short_colors': 0,  # Converts things like #RRGGBB to #RGB
    'reverse_colors': 0,  # Gets the shortest name of all for colors
}
