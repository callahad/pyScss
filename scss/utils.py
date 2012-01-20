# -*- coding: utf-8 -*-

import re


def to_str(num):
    if isinstance(num, dict):
        s = sorted(num.items())
        sp = num.get('_', '')
        return (sp + ' ').join(to_str(v) for n, v in s if n != '_')
    elif isinstance(num, float):
        num = ('%0.03f' % round(num, 3)).rstrip('0').rstrip('.')
        return num
    elif isinstance(num, bool):
        return 'true' if num else 'false'
    elif num is None:
        return ''
    return str(num)


def to_float(num):
    if isinstance(num, (float, int)):
        return float(num)
    num = to_str(num)
    if num and num[-1] == '%':
        return float(num[:-1]) / 100.0
    else:
        return float(num)


hex2rgba = {
    9: lambda c: (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16), int(c[7:9], 16)),
    7: lambda c: (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16), 1.0),
    5: lambda c: (int(c[1] * 2, 16), int(c[2] * 2, 16), int(c[3] * 2, 16), int(c[4] * 2, 16)),
    4: lambda c: (int(c[1] * 2, 16), int(c[2] * 2, 16), int(c[3] * 2, 16), 1.0),
}


def escape(s):
    return re.sub(r'''(["'])''', r'\\\1', s)


def unescape(s):
    return re.sub(r'''\\(['"])''', r'\1', s)


def dequote(s):
    if s and s[0] in ('"', "'") and s[-1] == s[0]:
        s = s[1:-1]
        s = unescape(s)
    return s


def depar(s):
    while s and s[0] == '(' and s[-1] == ')':
        s = s[1:-1]
    return s
