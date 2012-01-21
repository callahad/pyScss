# -*- coding: utf-8 -*-

import math

from .data_types import (BooleanValue, NumberValue, ListValue, ColorValue,
                         QuotedStringValue, StringValue)
from .regexes import _variable_re
from .units import _units_weights, _conv_type
from .utils import to_str


FILEID = 0
POSITION = 1
CODESTR = 2
DEPS = 3
CONTEXT = 4
OPTIONS = 5
SELECTORS = 6
PROPERTIES = 7
PATH = 8
INDEX = 9
LINENO = 10
FINAL = 11
MEDIA = 12
RULE_VARS = {
    'FILEID': FILEID,
    'POSITION': POSITION,
    'CODESTR': CODESTR,
    'DEPS': DEPS,
    'CONTEXT': CONTEXT,
    'OPTIONS': OPTIONS,
    'SELECTORS': SELECTORS,
    'PROPERTIES': PROPERTIES,
    'PATH': PATH,
    'INDEX': INDEX,
    'LINENO': LINENO,
    'FINAL': FINAL,
    'MEDIA': MEDIA,
}


################################################################################


__elements_of_type_block = 'address, article, aside, blockquote, center, dd, details, dir, div, dl, dt, fieldset, figcaption, figure, footer, form, frameset, h1, h2, h3, h4, h5, h6, header, hgroup, hr, isindex, menu, nav, noframes, noscript, ol, p, pre, section, summary, ul'
__elements_of_type_inline = 'a, abbr, acronym, audio, b, basefont, bdo, big, br, canvas, cite, code, command, datalist, dfn, em, embed, font, i, img, input, kbd, keygen, label, mark, meter, output, progress, q, rp, rt, ruby, s, samp, select, small, span, strike, strong, sub, sup, textarea, time, tt, u, var, video, wbr'
__elements_of_type_table = 'table'
__elements_of_type_list_item = 'li'
__elements_of_type_table_row_group = 'tbody'
__elements_of_type_table_header_group = 'thead'
__elements_of_type_table_footer_group = 'tfoot'
__elements_of_type_table_row = 'tr'
__elements_of_type_table_cel = 'td, th'
__elements_of_type_html5_block = 'article, aside, details, figcaption, figure, footer, header, hgroup, menu, nav, section, summary'
__elements_of_type_html5_inline = 'audio, canvas, command, datalist, embed, keygen, mark, meter, output, progress, rp, rt, ruby, time, video, wbr'
__elements_of_type_html5 = 'article, aside, audio, canvas, command, datalist, details, embed, figcaption, figure, footer, header, hgroup, keygen, mark, menu, meter, nav, output, progress, rp, rt, ruby, section, summary, time, video, wbr'
__elements_of_type = {
    'block': dict(enumerate(sorted(__elements_of_type_block.replace(' ', '').split(',')))),
    'inline': dict(enumerate(sorted(__elements_of_type_inline.replace(' ', '').split(',')))),
    'table': dict(enumerate(sorted(__elements_of_type_table.replace(' ', '').split(',')))),
    'list-item': dict(enumerate(sorted(__elements_of_type_list_item.replace(' ', '').split(',')))),
    'table-row-group': dict(enumerate(sorted(__elements_of_type_table_row_group.replace(' ', '').split(',')))),
    'table-header-group': dict(enumerate(sorted(__elements_of_type_table_header_group.replace(' ', '').split(',')))),
    'table-footer-group': dict(enumerate(sorted(__elements_of_type_table_footer_group.replace(' ', '').split(',')))),
    'table-row': dict(enumerate(sorted(__elements_of_type_table_footer_group.replace(' ', '').split(',')))),
    'table-cell': dict(enumerate(sorted(__elements_of_type_table_footer_group.replace(' ', '').split(',')))),
    'html5-block': dict(enumerate(sorted(__elements_of_type_html5_block.replace(' ', '').split(',')))),
    'html5-inline': dict(enumerate(sorted(__elements_of_type_html5_inline.replace(' ', '').split(',')))),
    'html5': dict(enumerate(sorted(__elements_of_type_html5.replace(' ', '').split(',')))),
}


def _elements_of_type(display):
    d = StringValue(display)
    ret = __elements_of_type.get(d.value, None)
    if ret is None:
        raise Exception("Elements of type '%s' not found!" % d.value)
    ret['_'] = ','
    return ListValue(ret)


def _nest(*arguments):
    if isinstance(arguments[0], ListValue):
        lst = arguments[0].values()
    else:
        lst = StringValue(arguments[0]).value.split(',')
    ret = [s.strip() for s in lst if s.strip()]
    for arg in arguments[1:]:
        if isinstance(arg, ListValue):
            lst = arg.values()
        else:
            lst = StringValue(arg).value.split(',')
        new_ret = []
        for s in lst:
            s = s.strip()
            if s:
                for r in ret:
                    new_ret.append(r + ' ' + s)
        ret = new_ret
    ret = sorted(set(ret))
    ret = dict(enumerate(ret))
    ret['_'] = ','
    return ret


def _append_selector(selector, to_append):
    if isinstance(selector, ListValue):
        lst = selector.values()
    else:
        lst = StringValue(selector).value.split(',')
    to_append = StringValue(to_append).value.strip()
    ret = sorted(set(s.strip() + to_append for s in lst if s.strip()))
    ret = dict(enumerate(ret))
    ret['_'] = ','
    return ret


def _headers(frm=None, to=None):
    if frm and to is None:
        if isinstance(frm, StringValue) and frm.value.lower() == 'all':
            frm = 1
            to = 6
        else:
            frm = 1
            try:
                to = int(getattr(frm, 'value', frm))
            except ValueError:
                to = 6
    else:
        try:
            frm = 1 if frm is None else int(getattr(frm, 'value', frm))
        except ValueError:
            frm = 1
        try:
            to = 6 if to is None else int(getattr(to, 'value', to))
        except ValueError:
            to = 6
    ret = ['h' + str(i) for i in range(frm, to + 1)]
    ret = dict(enumerate(ret))
    ret['_'] = ','
    return ret


def _enumerate(prefix, frm, through, separator='-'):
    prefix = StringValue(prefix).value
    separator = StringValue(separator).value
    try:
        frm = int(getattr(frm, 'value', frm))
    except ValueError:
        frm = 1
    try:
        through = int(getattr(through, 'value', through))
    except ValueError:
        through = frm
    if frm > through:
        frm, through = through, frm
        rev = reversed
    else:
        rev = lambda x: x
    if prefix:
        ret = [prefix + separator + str(i) for i in rev(range(frm, through + 1))]
    else:
        ret = [NumberValue(i) for i in rev(range(frm, through + 1))]
    ret = dict(enumerate(ret))
    ret['_'] = ','
    return ret


def _range(frm, through=None):
    if through is None:
        through = frm
        frm = 1
    return _enumerate(None, frm, through)


################################################################################


def __compass_list(*args):
    separator = None
    if len(args) == 1 and isinstance(args[0], (list, tuple, ListValue)):
        args = ListValue(args[0]).values()
    else:
        separator = ','
    ret = ListValue(args)
    if separator:
        ret['_'] = separator
    return ret


def __compass_space_list(*lst):
    """
    If the argument is a list, it will return a new list that is space delimited
    Otherwise it returns a new, single element, space-delimited list.
    """
    ret = __compass_list(*lst)
    ret.value.pop('_', None)
    return ret


def _blank(*objs):
    """Returns true when the object is false, an empty string, or an empty list"""
    for o in objs:
        if bool(o):
            return BooleanValue(False)
    return BooleanValue(True)


def _compact(*args):
    """Returns a new list after removing any non-true values"""
    ret = {}
    if len(args) == 1:
        args = args[0]
        if isinstance(args, ListValue):
            args = args.value
        if isinstance(args, dict):
            for i, item in args.items():
                if bool(item):
                    ret[i] = item
        elif bool(args):
            ret[0] = args
    else:
        ret['_'] = ','
        for i, item in enumerate(args):
            if bool(item):
                ret[i] = item
    if isinstance(args, ListValue):
        args = args.value
    if isinstance(args, dict):
        separator = args.get('_', None)
        if separator is not None:
            ret['_'] = separator
    return ListValue(ret)


def _reject(lst, *values):
    """Removes the given values from the list"""
    ret = {}
    if not isinstance(lst, ListValue):
        lst = ListValue(lst)
    lst = lst.value
    if len(values) == 1:
        values = values[0]
        if isinstance(values, ListValue):
            values = values.value.values()
    for i, item in lst.items():
        if item not in values:
            ret[i] = item
    separator = lst.get('_', None)
    if separator is not None:
        ret['_'] = separator
    return ListValue(ret)


def __compass_slice(lst, start_index, end_index=None):
    start_index = NumberValue(start_index).value
    end_index = NumberValue(end_index).value if end_index is not None else None
    ret = {}
    lst = ListValue(lst).value
    for i, item in lst.items():
        if not isinstance(i, int):
            if i == '_':
                ret[i] = item
        elif i > start_index and end_index is None or i <= end_index:
            ret[i] = item
    return ListValue(ret)


def _first_value_of(*lst):
    if len(lst) == 1 and isinstance(lst[0], (list, tuple, ListValue)):
        lst = ListValue(lst[0]).values()
    ret = ListValue(lst).first()
    return ret.__class__(ret)


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


def _max(*lst):
    if len(lst) == 1 and isinstance(lst[0], (list, tuple, ListValue)):
        lst = ListValue(lst[0]).values()
    lst = ListValue(lst).value
    return max(lst.values())


def _min(*lst):
    if len(lst) == 1 and isinstance(lst[0], (list, tuple, ListValue)):
        lst = ListValue(lst[0]).values()
    lst = ListValue(lst).value
    return min(lst.values())


def _append(lst, val, separator=None):
    separator = separator and StringValue(separator).value
    ret = ListValue(lst, separator)
    val = ListValue(val)
    for v in val:
        ret.value[len(ret)] = v
    return ret


################################################################################


def _prefixed(prefix, *args):
    to_fnct_str = 'to_' + to_str(prefix).replace('-', '_')
    for arg in args:
        if isinstance(arg, ListValue):
            for k, iarg in arg.value.items():
                if hasattr(iarg, to_fnct_str):
                    return BooleanValue(True)
        else:
            if hasattr(arg, to_fnct_str):
                return BooleanValue(True)
    return BooleanValue(False)


def _prefix(prefix, *args):
    to_fnct_str = 'to_' + to_str(prefix).replace('-', '_')
    args = list(args)
    for i, arg in enumerate(args):
        if isinstance(arg, ListValue):
            _value = {}
            for k, iarg in arg.value.items():
                to_fnct = getattr(iarg, to_fnct_str, None)
                if to_fnct:
                    _value[k] = to_fnct()
                else:
                    _value[k] = iarg
            args[i] = ListValue(_value)
        else:
            to_fnct = getattr(arg, to_fnct_str, None)
            if to_fnct:
                args[i] = to_fnct()
    if len(args) == 1:
        return args[0]
    return ListValue(args, ',')


def __moz(*args):
    return _prefix('_moz', *args)


def __svg(*args):
    return _prefix('_svg', *args)


def __css2(*args):
    return _prefix('_css2', *args)


def __pie(*args):
    return _prefix('_pie', *args)


def __webkit(*args):
    return _prefix('_webkit', *args)


def __owg(*args):
    return _prefix('_owg', *args)


def __khtml(*args):
    return _prefix('_khtml', *args)


def __ms(*args):
    return _prefix('_ms', *args)


def __o(*args):
    return _prefix('_o', *args)


################################################################################


def _percentage(value):
    value = NumberValue(value)
    value.units = {'%': _units_weights.get('%', 1), '_': '%'}
    return value


def _unitless(value):
    value = NumberValue(value)
    return BooleanValue(not bool(value.unit))


def _unquote(*args):
    return StringValue(' '.join([StringValue(s).value for s in args]))


def _quote(*args):
    return QuotedStringValue(' '.join([StringValue(s).value for s in args]))


def _pi():
    return NumberValue(math.pi)


def _comparable(number1, number2):
    n1, n2 = NumberValue(number1), NumberValue(number2)
    type1 = _conv_type.get(n1.unit)
    type2 = _conv_type.get(n2.unit)
    return BooleanValue(type1 == type2)


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


def _if(condition, if_true, if_false=''):
    condition = bool(False if not condition or isinstance(condition, basestring) and (condition in ('0', 'false', 'undefined') or _variable_re.match(condition)) else condition)
    return if_true.__class__(if_true) if condition else if_true.__class__(if_false)


def _unit(number):  # -> px, em, cm, etc.
    unit = NumberValue(number).unit
    return StringValue(unit)
