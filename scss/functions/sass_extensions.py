# -*- coding: utf-8 -*-

from .sass import _grayscale, _opacify, _transparentize

typos = {
    'fadein:2': _opacify,          # fade-in
    'fadeout:2': _transparentize,  # fade-out
    'greyscale:1': _grayscale      # grayscale
}
