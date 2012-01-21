# -*- coding: utf-8 -*-

# Via http://sass-lang.com/docs/yardoc/Sass/Script/Functions.html
# (Sass::SCript::Functions)

import colorsys
import math
import operator

from ..data_types import (BooleanValue, ColorValue, ListValue, NumberValue,
                          QuotedStringValue, StringValue, Value)
from ..regexes import _variable_re
from ..units import _conv_type, _units_weights


# RGB Functions


def _rgb(r, g, b, type='rgb'):
    return _rgba(r, g, b, 1.0, type)


def _rgba(r, g, b, a, type='rgba'):
    c = NumberValue(r), NumberValue(g), NumberValue(b), NumberValue(a)

    col = [c[i].value * 255.0 if (c[i].unit == '%' or c[i].value > 0 and c[i].value <= 1) else
            0.0 if c[i].value < 0 else
            255.0 if c[i].value > 255 else
            c[i].value
            for i in range(3)
          ]
    col += [0.0 if c[3].value < 0 else 1.0 if c[3].value > 1 else c[3].value]
    col += [type]
    return ColorValue(col)


def _rgba2(color, a=None):
    return _color_type(color, a, 'rgba')


def _red(color):
    c = ColorValue(color).value
    return NumberValue(c[0])


def _green(color):
    c = ColorValue(color).value
    return NumberValue(c[1])


def _blue(color):
    c = ColorValue(color).value
    return NumberValue(c[2])


def _mix(color1, color2, weight=None):
    """
    Mixes together two colors. Specifically, takes the average of each of the
    RGB components, optionally weighted by the given percentage.
    The opacity of the colors is also considered when weighting the components.

    Specifically, takes the average of each of the RGB components,
    optionally weighted by the given percentage.
    The opacity of the colors is also considered when weighting the components.

    The weight specifies the amount of the first color that should be included
    in the returned color.
    50%, means that half the first color
        and half the second color should be used.
    25% means that a quarter of the first color
        and three quarters of the second color should be used.

    For example:

        mix(#f00, #00f) => #7f007f
        mix(#f00, #00f, 25%) => #3f00bf
        mix(rgba(255, 0, 0, 0.5), #00f) => rgba(63, 0, 191, 0.75)

    """
    # This algorithm factors in both the user-provided weight
    # and the difference between the alpha values of the two colors
    # to decide how to perform the weighted average of the two RGB values.
    #
    # It works by first normalizing both parameters to be within [-1, 1],
    # where 1 indicates "only use color1", -1 indicates "only use color 0",
    # and all values in between indicated a proportionately weighted average.
    #
    # Once we have the normalized variables w and a,
    # we apply the formula (w + a)/(1 + w*a)
    # to get the combined weight (in [-1, 1]) of color1.
    # This formula has two especially nice properties:
    #
    #   * When either w or a are -1 or 1, the combined weight is also that number
    #     (cases where w * a == -1 are undefined, and handled as a special case).
    #
    #   * When a is 0, the combined weight is w, and vice versa
    #
    # Finally, the weight of color1 is renormalized to be within [0, 1]
    # and the weight of color2 is given by 1 minus the weight of color1.
    #
    # Algorithm from the Sass project: http://sass-lang.com/

    c1 = ColorValue(color1).value
    c2 = ColorValue(color2).value
    p = NumberValue(weight).value if weight is not None else 0.5
    p = 0.0 if p < 0 else 1.0 if p > 1 else p

    w = p * 2 - 1
    a = c1[3] - c2[3]

    w1 = ((w if (w * a == -1) else (w + a) / (1 + w * a)) + 1) / 2.0

    w2 = 1 - w1
    q = [w1, w1, w1, p]
    r = [w2, w2, w2, 1 - p]

    color = ColorValue(None).merge(c1).merge(c2)
    color.value = [c1[i] * q[i] + c2[i] * r[i] for i in range(4)]

    return color


# HSL Functions


def _hsl(h, s, l, type='hsl'):
    return _hsla(h, s, l, 1.0, type)


def _hsla(h, s, l, a, type='hsla'):
    c = NumberValue(h), NumberValue(s), NumberValue(l), NumberValue(a)
    col = [c[0] if (c[0].unit == '%' and c[0].value > 0 and c[0].value <= 1) else (c[0].value % 360.0) / 360.0]
    col += [0.0 if cl <= 0 else 1.0 if cl >= 1.0 else cl
            for cl in [
                c[i].value if (c[i].unit == '%' or c[i].value > 0 and c[i].value <= 1) else
                c[i].value / 100.0
                for i in range(1, 4)
              ]
           ]
    col += [type]
    c = [c * 255.0 for c in colorsys.hls_to_rgb(col[0], 0.999999 if col[2] == 1 else col[2], 0.999999 if col[1] == 1 else col[1])] + [col[3], type]
    col = ColorValue(c)
    return col


def _hue(color):
    c = ColorValue(color).value
    h, l, s = colorsys.rgb_to_hls(c[0] / 255.0, c[1] / 255.0, c[2] / 255.0)
    ret = NumberValue(h * 360.0)
    ret.units = {'deg': _units_weights.get('deg', 1), '_': 'deg'}
    return ret


def _saturation(color):
    c = ColorValue(color).value
    h, l, s = colorsys.rgb_to_hls(c[0] / 255.0, c[1] / 255.0, c[2] / 255.0)
    ret = NumberValue(s)
    ret.units = {'%': _units_weights.get('%', 1), '_': '%'}
    return ret


def _lightness(color):
    c = ColorValue(color).value
    h, l, s = colorsys.rgb_to_hls(c[0] / 255.0, c[1] / 255.0, c[2] / 255.0)
    ret = NumberValue(l)
    ret.units = {'%': _units_weights.get('%', 1), '_': '%'}
    return ret


def _adjust_hue(color, degrees):
    return __hsl_op(operator.__add__, color, degrees, 0, 0)


def _lighten(color, amount):
    return __hsl_op(operator.__add__, color, 0, 0, amount)


def _darken(color, amount):
    return __hsl_op(operator.__sub__, color, 0, 0, amount)


def _saturate(color, amount):
    return __hsl_op(operator.__add__, color, 0, amount, 0)


def _desaturate(color, amount):
    return __hsl_op(operator.__sub__, color, 0, amount, 0)


def _grayscale(color):
    return __hsl_op(operator.__sub__, color, 0, 100.0, 0)


def _complement(color):
    return __hsl_op(operator.__add__, color, 180.0, 0, 0)


def _invert(color):
    """
    Returns the inverse (negative) of a color.
    The red, green, and blue values are inverted, while the opacity is left alone.
    """
    col = ColorValue(color)
    c = col.value
    c[0] = 255.0 - c[0]
    c[1] = 255.0 - c[1]
    c[2] = 255.0 - c[2]
    return col


# Opacity Functions


def _alpha(color):
    c = ColorValue(color).value
    return NumberValue(c[3])


def _opacify(color, amount):
    return __rgba_op(operator.__add__, color, 0, 0, 0, amount)


def _transparentize(color, amount):
    return __rgba_op(operator.__sub__, color, 0, 0, 0, amount)


# Other Color Functions


def _adjust_color(color, saturation=None, lightness=None, red=None, green=None, blue=None, alpha=None):
    return _asc_color(operator.__add__, color, saturation, lightness, red, green, blue, alpha)


def _scale_color(color, saturation=None, lightness=None, red=None, green=None, blue=None, alpha=None):
    return _asc_color(operator.__mul__, color, saturation, lightness, red, green, blue, alpha)


def _change_color(color, saturation=None, lightness=None, red=None, green=None, blue=None, alpha=None):
    return _asc_color(None, color, saturation, lightness, red, green, blue, alpha)


# String Functions


def _unquote(*args):
    return StringValue(' '.join([StringValue(s).value for s in args]))


def _quote(*args):
    return QuotedStringValue(' '.join([StringValue(s).value for s in args]))


# Number Functions


def _percentage(value):
    value = NumberValue(value)
    value.units = {'%': _units_weights.get('%', 1), '_': '%'}
    return value


# List Functions


def _nth(lst, n=1):
    """
    Return the Nth item in the string
    """
    n = StringValue(n).value
    lst = ListValue(lst).value
    try:
        n = int(float(n)) - 1
        n = n % len(lst)
    except:
        if n.lower() == 'first':
            n = 0
        elif n.lower() == 'last':
            n = -1
    try:
        ret = lst[n]
    except KeyError:
        lst = [v for k, v in sorted(lst.items()) if isinstance(k, int)]
        try:
            ret = lst[n]
        except:
            ret = ''
    return ret.__class__(ret)


def _join(lst1, lst2, separator=None):
    ret = ListValue(lst1)
    lst2 = ListValue(lst2).value
    lst_len = len(ret.value)
    ret.value.update((k + lst_len if isinstance(k, int) else k, v) for k, v in lst2.items())
    if separator is not None:
        separator = StringValue(separator).value
        if separator:
            ret.value['_'] = separator
    return ret


def _length(*lst):
    if len(lst) == 1 and isinstance(lst[0], (list, tuple, ListValue)):
        lst = ListValue(lst[0]).values()
    lst = ListValue(lst)
    return NumberValue(len(lst))


# Introspection Functions


def _type_of(obj):  # -> bool, number, string, color, list
    if isinstance(obj, BooleanValue):
        return StringValue('bool')
    if isinstance(obj, NumberValue):
        return StringValue('number')
    if isinstance(obj, ColorValue):
        return StringValue('color')
    if isinstance(obj, ListValue):
        return StringValue('list')
    if isinstance(obj, basestring) and _variable_re.match(obj):
        return StringValue('undefined')
    return StringValue('string')


def _unit(number):  # -> px, em, cm, etc.
    unit = NumberValue(number).unit
    return StringValue(unit)


def _unitless(value):
    value = NumberValue(value)
    return BooleanValue(not bool(value.unit))


def _comparable(number1, number2):
    n1, n2 = NumberValue(number1), NumberValue(number2)
    type1 = _conv_type.get(n1.unit)
    type2 = _conv_type.get(n2.unit)
    return BooleanValue(type1 == type2)


# Miscellaneous Functions


def _if(condition, if_true, if_false=''):
    condition = bool(False if not condition or isinstance(condition, basestring) and (condition in ('0', 'false', 'undefined') or _variable_re.match(condition)) else condition)
    return if_true.__class__(if_true) if condition else if_true.__class__(if_false)


# Internal Helpers


def _color_type(color, a, type):
    color = ColorValue(color).value
    a = NumberValue(a).value if a is not None else color[3]
    col = list(color[:3])
    col += [0.0 if a < 0 else 1.0 if a > 1 else a]
    col += [type]
    return ColorValue(col)


def __rgba_op(op, color, r, g, b, a):
    color = ColorValue(color)
    c = color.value
    a = [
        None if r is None else NumberValue(r).value,
        None if g is None else NumberValue(g).value,
        None if b is None else NumberValue(b).value,
        None if a is None else NumberValue(a).value,
    ]
    # Do the additions:
    c = [op(c[i], a[i]) if op is not None and a[i] is not None else a[i] if a[i] is not None else c[i] for i in range(4)]
    # Validations:
    r = 255.0, 255.0, 255.0, 1.0
    c = [0.0 if c[i] < 0 else r[i] if c[i] > r[i] else c[i] for i in range(4)]
    color.value = tuple(c)
    return color


def _asc_color(op, color, saturation=None, lightness=None, red=None, green=None, blue=None, alpha=None):
    if lightness or saturation:
        color = __hsl_op(op, color, 0, saturation, lightness)
    if red or green or blue or alpha:
        color = __rgba_op(op, color, red, green, blue, alpha)
    return color


def __hsl_op(op, color, h, s, l):
    color = ColorValue(color)
    c = color.value
    h = None if h is None else NumberValue(h)
    s = None if s is None else NumberValue(s)
    l = None if l is None else NumberValue(l)
    a = [
        None if h is None else h.value / 360.0,
        None if s is None else s.value / 100.0 if s.unit != '%' and s.value >= 1 else s.value,
        None if l is None else l.value / 100.0 if l.unit != '%' and l.value >= 1 else l.value,
    ]
    # Convert to HSL:
    h, l, s = list(colorsys.rgb_to_hls(c[0] / 255.0, c[1] / 255.0, c[2] / 255.0))
    c = h, s, l
    # Do the additions:
    c = [0.0 if c[i] < 0 else 1.0 if c[i] > 1 else op(c[i], a[i]) if op is not None and a[i] is not None else a[i] if a[i] is not None else c[i] for i in range(3)]
    # Validations:
    c[0] = (c[0] * 360.0) % 360
    r = 360.0, 1.0, 1.0
    c = [0.0 if c[i] < 0 else r[i] if c[i] > r[i] else c[i] for i in range(3)]
    # Convert back to RGB:
    c = colorsys.hls_to_rgb(c[0] / 360.0, 0.999999 if c[2] == 1 else c[2], 0.999999 if c[1] == 1 else c[1])
    color.value = (c[0] * 255.0, c[1] * 255.0, c[2] * 255.0, color.value[3])
    return color


# PyScss Setup

sass_functions = {}

sass_functions.update({
    'rgb:3': _rgb,
    'rgba:4': _rgba,
    'rgba:2': _rgba2,
    'red:1': _red,
    'green:1': _green,
    'blue:1': _blue,
    'mix:2': _mix,
    'mix:3': _mix,
})

sass_functions.update({
    'hsl:3': _hsl,
    'hsla:4': _hsla,
    'hue:1': _hue,
    'saturation:1': _saturation,
    'lightness:1': _lightness,
    'adjust-hue:2': _adjust_hue,
    'lighten:2': _lighten,
    'darken:2': _darken,
    'saturate:2': _saturate,
    'desaturate:2': _desaturate,
    'grayscale:1': _grayscale,
    'complement:1': _complement,
    'invert:1': _invert,
})

sass_functions.update({
    'alpha:1': _alpha,
    'opacity:1': _alpha,
    'opacify:2': _opacify,
    'fade-in:2': _opacify,
    'transparentize:2': _transparentize,
    'fade-out:2': _transparentize,
})

sass_functions.update({
    'adjust-color:n': _adjust_color,
    'scale-color:n': _scale_color,
    'change-color:n': _change_color,
})

sass_functions.update({
    'unquote:n': _unquote,
    'quote:n': _quote,
})

sass_functions.update({
    'percentage:1': _percentage,
    'round:1': Value._wrap(round),
    'ceil:1': Value._wrap(math.ceil),
    'floor:1': Value._wrap(math.floor),
})

sass_functions.update({
    'length:n': _length,
    'nth:2': _nth,
    'join:2': _join,
    'join:3': _join,
})

sass_functions.update({
    'type-of:1': _type_of,
    'unit:1': _unit,
    'unitless:1': _unitless,
    'comparable:2': _comparable,
})

sass_functions.update({
    'if:3': _if,
})
