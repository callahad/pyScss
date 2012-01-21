# -*- coding: utf-8 -*-

try:
    import cPickle as pickle
except ImportError:
    import pickle

try:
    import cStringIO as StringIO
except:
    import StringIO

try:
    from PIL import Image, ImageDraw
except ImportError:
    try:
        import Image, ImageDraw
    except:
        Image = None

import os
import base64
import datetime
import glob
import hashlib
import math
import mimetypes
import operator
import random
import time

from ..config import ASSETS_URL, STATIC_URL, _cfg, log
from ..data_types import (Value, NumberValue, ListValue, ColorValue,
                         QuotedStringValue, StringValue)
from ..support import (__compass_list, __compass_slice, __compass_space_list,
                       __css2, __moz, __ms, __o, __owg, __pie, __svg, __webkit,
                       _append, _append_selector, _blank, _compact,
                       _elements_of_type, _enumerate, _first_value_of, _headers,
                       _max, _min, _nest,
                       _pi, _prefix, _prefixed, _range,
                       _reject)
from ..units import _units, _units_weights
from ..utils import escape, split_params, to_float, to_str
from .sass import (_color_type, __hsl_op, _opacify, _transparentize,
                   _grayscale, _adjust_hue, _rgba2, _nth, _length, _unquote,
                   _if, func_mapping)


################################################################################
# Sass/Compass Library Functions:


def _rgb2(color):
    return _color_type(color, 1.0, 'rgb')


def _hsl2(color):
    return _color_type(color, 1.0, 'hsl')


def _hsla2(color, a=None):
    return _color_type(color, a, 'hsla')


def _ie_hex_str(color):
    c = ColorValue(color).value
    return StringValue('#%02X%02X%02X%02X' % (round(c[3] * 255), round(c[0]), round(c[1]), round(c[2])))




def _adjust_lightness(color, amount):
    return __hsl_op(operator.__add__, color, 0, 0, amount)


def _adjust_saturation(color, amount):
    return __hsl_op(operator.__add__, color, 0, amount, 0)


def _scale_lightness(color, amount):
    return __hsl_op(operator.__mul__, color, 0, 0, amount)


def _scale_saturation(color, amount):
    return __hsl_op(operator.__mul__, color, 0, amount, 0)


def __color_stops(percentages, *args):
    if len(args) == 1:
        if isinstance(args[0], (list, tuple, ListValue)):
            return ListValue(args[0]).values()
        elif isinstance(args[0], (StringValue, basestring)):
            color_stops = []
            colors = split_params(args[0].value)
            for color in colors:
                color = color.strip()
                if color.startswith('color-stop('):
                    s, c = split_params(color[11:].rstrip(')'))
                    s = s.strip()
                    c = c.strip()
                else:
                    c, s = color.split()
                color_stops.append((to_float(s), c))
            return color_stops

    colors = []
    stops = []
    prev_color = False
    for c in args:
        if isinstance(c, ListValue):
            for i, c in c.items():
                if isinstance(c, ColorValue):
                    if prev_color:
                        stops.append(None)
                    colors.append(c)
                    prev_color = True
                elif isinstance(c, NumberValue):
                    stops.append(c)
                    prev_color = False
        else:
            if isinstance(c, ColorValue):
                if prev_color:
                    stops.append(None)
                colors.append(c)
                prev_color = True
            elif isinstance(c, NumberValue):
                stops.append(NumberValue(c))
                prev_color = False
    if prev_color:
        stops.append(None)
    stops = stops[:len(colors)]
    if percentages:
        max_stops = max(s and (s.value if s.unit != '%' else None) or None for s in stops)
    else:
        max_stops = max(s and (s if s.unit != '%' else None) or None for s in stops)
    stops = [s and (s.value / max_stops if s.unit != '%' else s.value) for s in stops]
    stops[0] = 0

    init = 0
    start = None
    for i, s in enumerate(stops + [1.0]):
        if s is None:
            if start is None:
                start = i
            end = i
        else:
            final = s
            if start is not None:
                stride = (final - init) / (end - start + 1 + (1 if i < len(stops) else 0))
                for j in range(start, end + 1):
                    stops[j] = init + stride * (j - start + 1)
            init = final
            start = None

    if not max_stops or percentages:
        stops = [NumberValue(s, '%') for s in stops]
    else:
        stops = [s * max_stops for s in stops]
    return zip(stops, colors)


def _grad_color_stops(*args):
    if len(args) == 1 and isinstance(args[0], (list, tuple, ListValue)):
        args = ListValue(args[0]).values()
    color_stops = __color_stops(True, *args)
    ret = ', '.join(['color-stop(%s, %s)' % (to_str(s), c) for s, c in color_stops])
    return StringValue(ret)


def __grad_end_position(radial, color_stops):
    return __grad_position(-1, 100, radial, color_stops)


def __grad_position(index, default, radial, color_stops):
    try:
        stops = NumberValue(color_stops[index][0])
        if radial and stops.unit != 'px' and (index == 0 or index == -1 or index == len(color_stops) - 1):
            log.warn("Webkit only supports pixels for the start and end stops for radial gradients. Got %s", stops)
    except IndexError:
        stops = NumberValue(default)
    return stops


def _grad_end_position(*color_stops):
    color_stops = __color_stops(False, *color_stops)
    return NumberValue(__grad_end_position(False, color_stops))


def _color_stops(*args):
    if len(args) == 1 and isinstance(args[0], (list, tuple, ListValue)):
        args = ListValue(args[0]).values()
    color_stops = __color_stops(False, *args)
    ret = ', '.join(['%s %s' % (c, to_str(s)) for s, c in color_stops])
    return StringValue(ret)


def _color_stops_in_percentages(*args):
    if len(args) == 1 and isinstance(args[0], (list, tuple, ListValue)):
        args = ListValue(args[0]).values()
    color_stops = __color_stops(True, *args)
    ret = ', '.join(['%s %s' % (c, to_str(s)) for s, c in color_stops])
    return StringValue(ret)


def _radial_gradient(*args):
    if len(args) == 1 and isinstance(args[0], (list, tuple, ListValue)):
        args = ListValue(args[0]).values()
    color_stops = args
    position_and_angle = None
    shape_and_size = None
    if isinstance(args[0], (StringValue, NumberValue, basestring)):
        position_and_angle = args[0]
        if isinstance(args[1], (StringValue, NumberValue, basestring)):
            shape_and_size = args[1]
            color_stops = args[2:]
        else:
            color_stops = args[1:]
    color_stops = __color_stops(False, *color_stops)

    args = [
        position_and_angle if position_and_angle is not None else None,
        shape_and_size if shape_and_size is not None else None,
    ]
    args.extend('%s %s' % (c, to_str(s)) for s, c in color_stops)
    to__s = 'radial-gradient(' + ', '.join(to_str(a) for a in args or [] if a is not None) + ')'
    ret = StringValue(to__s)

    def to__moz():
        return StringValue('-moz-' + to__s)
    ret.to__moz = to__moz

    def to__pie():
        log.warn("PIE does not support radial-gradient.")
        return StringValue('-pie-radial-gradient(unsupported)')
    ret.to__pie = to__pie

    def to__css2():
        return StringValue('')
    ret.to__css2 = to__css2

    def to__webkit():
        return StringValue('-webkit-' + to__s)
    ret.to__webkit = to__webkit

    def to__owg():
        args = [
            'radial',
            _grad_point(position_and_angle) if position_and_angle is not None else 'center',
            '0',
            _grad_point(position_and_angle) if position_and_angle is not None else 'center',
            __grad_end_position(True, color_stops),
        ]
        args.extend('color-stop(%s, %s)' % (to_str(s), c) for s, c in color_stops)
        ret = '-webkit-gradient(' + ', '.join(to_str(a) for a in args or [] if a is not None) + ')'
        return StringValue(ret)
    ret.to__owg = to__owg

    def to__svg():
        return _radial_svg_gradient(color_stops, position_and_angle or 'center')
    ret.to__svg = to__svg

    return ret


def _linear_gradient(*args):
    if len(args) == 1 and isinstance(args[0], (list, tuple, ListValue)):
        args = ListValue(args[0]).values()
    color_stops = args
    position_and_angle = None
    if isinstance(args[0], (StringValue, NumberValue, basestring)):
        position_and_angle = args[0]
        color_stops = args[1:]
    color_stops = __color_stops(False, *color_stops)

    args = [
        _position(position_and_angle) if position_and_angle is not None else None,
    ]
    args.extend('%s %s' % (c, to_str(s)) for s, c in color_stops)
    to__s = 'linear-gradient(' + ', '.join(to_str(a) for a in args or [] if a is not None) + ')'
    ret = StringValue(to__s)

    def to__moz():
        return StringValue('-moz-' + to__s)
    ret.to__moz = to__moz

    def to__pie():
        return StringValue('-pie-' + to__s)
    ret.to__pie = to__pie

    def to__ms():
        return StringValue('-ms-' + to__s)
    ret.to__ms = to__ms

    def to__o():
        return StringValue('-o-' + to__s)
    ret.to__o = to__o

    def to__css2():
        return StringValue('')
    ret.to__css2 = to__css2

    def to__webkit():
        return StringValue('-webkit-' + to__s)
    ret.to__webkit = to__webkit

    def to__owg():
        args = [
            'linear',
            _position(position_and_angle or 'center top'),
            _opposite_position(position_and_angle or 'center top'),
        ]
        args.extend('color-stop(%s, %s)' % (to_str(s), c) for s, c in color_stops)
        ret = '-webkit-gradient(' + ', '.join(to_str(a) for a in args or [] if a is not None) + ')'
        return StringValue(ret)
    ret.to__owg = to__owg

    def to__svg():
        return _linear_svg_gradient(color_stops, position_and_angle or 'top')
    ret.to__svg = to__svg

    return ret


def _radial_svg_gradient(*args):
    if len(args) == 1 and isinstance(args[0], (list, tuple, ListValue)):
        args = ListValue(args[0]).values()
    color_stops = args
    center = None
    if isinstance(args[-1], (StringValue, NumberValue, basestring)):
        center = args[-1]
        color_stops = args[:-1]
    color_stops = __color_stops(False, *color_stops)
    cx, cy = zip(*_grad_point(center).items())[1]
    r = __grad_end_position(True, color_stops)
    svg = __radial_svg(color_stops, cx, cy, r)
    url = 'data:' + 'image/svg+xml' + ';base64,' + base64.b64encode(svg)
    inline = 'url("%s")' % escape(url)
    return StringValue(inline)


def _linear_svg_gradient(*args):
    if len(args) == 1 and isinstance(args[0], (list, tuple, ListValue)):
        args = ListValue(args[0]).values()
    color_stops = args
    start = None
    if isinstance(args[-1], (StringValue, NumberValue, basestring)):
        start = args[-1]
        color_stops = args[:-1]
    color_stops = __color_stops(False, *color_stops)
    x1, y1 = zip(*_grad_point(start).items())[1]
    x2, y2 = zip(*_grad_point(_opposite_position(start)).items())[1]
    svg = __linear_svg(color_stops, x1, y1, x2, y2)
    url = 'data:' + 'image/svg+xml' + ';base64,' + base64.b64encode(svg)
    inline = 'url("%s")' % escape(url)
    return StringValue(inline)


def __color_stops_svg(color_stops):
    ret = ''.join('<stop offset="%s" stop-color="%s"/>' % (to_str(s), c) for s, c in color_stops)
    return ret


def __svg_template(gradient):
    ret = '<?xml version="1.0" encoding="utf-8"?>\
<svg version="1.1" xmlns="http://www.w3.org/2000/svg">\
<defs>%s</defs>\
<rect x="0" y="0" width="100%%" height="100%%" fill="url(#grad)" />\
</svg>' % gradient
    return ret


def __linear_svg(color_stops, x1, y1, x2, y2):
    gradient = '<linearGradient id="grad" x1="%s" y1="%s" x2="%s" y2="%s">%s</linearGradient>' % (
        to_str(NumberValue(x1)),
        to_str(NumberValue(y1)),
        to_str(NumberValue(x2)),
        to_str(NumberValue(y2)),
        __color_stops_svg(color_stops)
    )
    return __svg_template(gradient)


def __radial_svg(color_stops, cx, cy, r):
    gradient = '<radialGradient id="grad" gradientUnits="userSpaceOnUse" cx="%s" cy="%s" r="%s">%s</radialGradient>' % (
        to_str(NumberValue(cx)),
        to_str(NumberValue(cy)),
        to_str(NumberValue(r)),
        __color_stops_svg(color_stops)
    )
    return __svg_template(gradient)


################################################################################
# Compass like functionality for sprites and images:
sprite_maps = {}
sprite_images = {}


def _sprite_map(g, **kwargs):
    """
    Generates a sprite map from the files matching the glob pattern.
    Uses the keyword-style arguments passed in to control the placement.
    """
    g = StringValue(g).value

    if not Image:
        raise Exception("Images manipulation require PIL")

    if g in sprite_maps:
        sprite_maps[glob]['*'] = datetime.datetime.now()
    elif '..' not in g:  # Protect against going to prohibited places...
        vertical = (kwargs.get('direction', 'vertical') == 'vertical')
        offset_x = NumberValue(kwargs.get('offset_x', 0))
        offset_y = NumberValue(kwargs.get('offset_y', 0))
        repeat = StringValue(kwargs.get('repeat', 'no-repeat'))
        position = NumberValue(kwargs.get('position', 0))
        dst_color = kwargs.get('dst_color')
        src_color = kwargs.get('src_color')
        if position and position > -1 and position < 1:
            position.units = {'%': _units_weights.get('%', 1), '_': '%'}
        spacing = kwargs.get('spacing', 0)
        if isinstance(spacing, ListValue):
            spacing = [int(NumberValue(v).value) for n, v in spacing.items()]
        else:
            spacing = [int(NumberValue(spacing).value)]
        spacing = (spacing * 4)[:4]

        if callable(_cfg['STATIC_ROOT']):
            rfiles = files = sorted(_cfg['STATIC_ROOT'](g))
        else:
            glob_path = os.path.join(_cfg['STATIC_ROOT'], g)
            files = glob.glob(glob_path)
            files = sorted((f, None) for f in files)
            rfiles = [(f[len(_cfg['STATIC_ROOT']):], s) for f, s in files]

        if not files:
            log.error("Nothing found at '%s'", glob_path)
            return StringValue(None)

        times = []
        for file, storage in files:
            try:
                d_obj = storage.modified_time(file)
                times.append(int(time.mktime(d_obj.timetuple())))
            except:
                times.append(int(os.path.getmtime(file)))

        map_name = os.path.normpath(os.path.dirname(g)).replace('\\', '_').replace('/', '_')
        key = list(zip(*files)[0]) + times + [repr(kwargs)]
        key = map_name + '-' + base64.urlsafe_b64encode(hashlib.md5(repr(key)).digest()).rstrip('=').replace('-', '_')
        asset_file = key + '.png'
        asset_path = os.path.join(_cfg['ASSETS_ROOT'], asset_file)

        if os.path.exists(asset_path + '.cache'):
            asset, map, sizes = pickle.load(open(asset_path + '.cache'))
            sprite_maps[asset] = map
        else:
            images = tuple(Image.open(storage.open(file)) if storage is not None else Image.open(file) for file, storage in files)
            names = tuple(os.path.splitext(os.path.basename(file))[0] for file, storage in files)
            positions = []
            spacings = []
            tot_spacings = []
            for name in names:
                name = name.replace('-', '_')
                _position = kwargs.get(name + '_position')
                if _position is None:
                    _position = position
                else:
                    _position = NumberValue(_position)
                    if _position and _position > -1 and _position < 1:
                        _position.units = {'%': _units_weights.get('%', 1), '_': '%'}
                positions.append(_position)
                _spacing = kwargs.get(name + '_spacing')
                if _spacing is None:
                    _spacing = spacing
                else:
                    if isinstance(_spacing, ListValue):
                        _spacing = [int(NumberValue(v).value) for n, v in _spacing.items()]
                    else:
                        _spacing = [int(NumberValue(_spacing).value)]
                    _spacing = (_spacing * 4)[:4]
                spacings.append(_spacing)
                if _position and _position.unit != '%':
                    if vertical:
                        if _position > 0:
                            tot_spacings.append((_spacing[0], _spacing[1], _spacing[2], _spacing[3] + _position))
                    else:
                        if _position > 0:
                            tot_spacings.append((_spacing[0] + _position, _spacing[1], _spacing[2], _spacing[3]))
                else:
                    tot_spacings.append(_spacing)
            sizes = tuple(image.size for image in images)

            _spacings = zip(*tot_spacings)
            if vertical:
                width = max(zip(*sizes)[0]) + max(_spacings[1]) + max(_spacings[3])
                height = sum(zip(*sizes)[1]) + sum(_spacings[0]) + sum(_spacings[2])
            else:
                width = sum(zip(*sizes)[0]) + sum(_spacings[1]) + sum(_spacings[3])
                height = max(zip(*sizes)[1]) + max(_spacings[0]) + max(_spacings[2])

            new_image = Image.new(
                mode='RGBA',
                size=(width, height),
                color=(0, 0, 0, 0)
            )

            offsets_x = []
            offsets_y = []
            offset = 0
            for i, image in enumerate(images):
                spacing = spacings[i]
                position = positions[i]
                if vertical:
                    if position and position.unit == '%':
                        x = width * position.value - (spacing[3] + sizes[i][1] + spacing[1])
                    elif position.value < 0:
                        x = width + position.value - (spacing[3] + sizes[i][1] + spacing[1])
                    else:
                        x = position.value
                    offset += spacing[0]
                    new_image.paste(image, (int(x + spacing[3]), offset))
                    offsets_x.append(x)
                    offsets_y.append(offset - spacing[0])
                    offset += sizes[i][1] + spacing[2]
                else:
                    if position and position.unit == '%':
                        y = height * position.value - (spacing[0] + sizes[i][1] + spacing[2])
                    elif position.value < 0:
                        y = height + position.value - (spacing[0] + sizes[i][1] + spacing[2])
                    else:
                        y = position.value
                    offset += spacing[3]
                    new_image.paste(image, (offset, int(y + spacing[0])))
                    offsets_x.append(offset - spacing[3])
                    offsets_y.append(y)
                    offset += sizes[i][0] + spacing[1]

            if dst_color:
                src_color = ColorValue(src_color).value[:3] if src_color else (0, 0, 0)
                dst_color = list(ColorValue(dst_color).value[:3])
                pixdata = new_image.load()
                for y in xrange(new_image.size[1]):
                    for x in xrange(new_image.size[0]):
                        if pixdata[x, y][:3] == src_color:
                            pixdata[x, y] = tuple(dst_color + [pixdata[x, y][3]])

            try:
                new_image.save(asset_path)
            except IOError:
                log.exception("Error while saving image")
            filetime = int(time.mktime(datetime.datetime.now().timetuple()))

            url = '%s%s?_=%s' % (ASSETS_URL, asset_file, filetime)
            asset = 'url("%s") %s' % (escape(url), repeat)
            # Use the sorted list to remove older elements (keep only 500 objects):
            if len(sprite_maps) > 1000:
                for a in sorted(sprite_maps, key=lambda a: sprite_maps[a]['*'], reverse=True)[500:]:
                    del sprite_maps[a]
            # Add the new object:
            map = dict(zip(names, zip(sizes, rfiles, offsets_x, offsets_y)))
            map['*'] = datetime.datetime.now()
            map['*f*'] = asset_file
            map['*k*'] = key
            map['*n*'] = map_name
            map['*t*'] = filetime
            pickle.dump((asset, map, zip(files, sizes)), open(asset_path + '.cache', 'w'))
            sprite_maps[asset] = map
        for file, size in sizes:
            sprite_images[file] = size
    ret = StringValue(asset)
    return ret


def _grid_image(left_gutter, width, right_gutter, height, columns=1, grid_color=None, baseline_color=None, background_color=None, inline=False):
    if not Image:
        raise Exception("Images manipulation require PIL")
    if grid_color == None:
        grid_color = (120, 170, 250, 15)
    else:
        c = ColorValue(grid_color).value
        grid_color = (c[0], c[1], c[2], int(c[3] * 255.0))
    if baseline_color == None:
        baseline_color = (120, 170, 250, 30)
    else:
        c = ColorValue(baseline_color).value
        baseline_color = (c[0], c[1], c[2], int(c[3] * 255.0))
    if background_color == None:
        background_color = (0, 0, 0, 0)
    else:
        c = ColorValue(background_color).value
        background_color = (c[0], c[1], c[2], int(c[3] * 255.0))
    _height = int(height) if height >= 1 else int(height * 1000.0)
    _width = int(width) if width >= 1 else int(width * 1000.0)
    _left_gutter = int(left_gutter) if left_gutter >= 1 else int(left_gutter * 1000.0)
    _right_gutter = int(right_gutter) if right_gutter >= 1 else int(right_gutter * 1000.0)
    if _height <= 0 or _width <= 0 or _left_gutter <= 0 or _right_gutter <= 0:
        raise ValueError
    _full_width = (_left_gutter + _width + _right_gutter)
    new_image = Image.new(
        mode='RGBA',
        size=(_full_width * int(columns), _height),
        color=background_color
    )
    draw = ImageDraw.Draw(new_image)
    for i in range(int(columns)):
        draw.rectangle((i * _full_width + _left_gutter, 0, i * _full_width + _left_gutter + _width - 1, _height - 1),  fill=grid_color)
    if _height > 1:
        draw.rectangle((0, _height - 1, _full_width * int(columns) - 1, _height - 1),  fill=baseline_color)
    if not inline:
        grid_name = 'grid_'
        if left_gutter:
            grid_name += str(int(left_gutter)) + '+'
        grid_name += str(int(width))
        if right_gutter:
            grid_name += '+' + str(int(right_gutter))
        if height and height > 1:
            grid_name += 'x' + str(int(height))
        key = (columns, grid_color, baseline_color, background_color)
        key = grid_name + '-' + base64.urlsafe_b64encode(hashlib.md5(repr(key)).digest()).rstrip('=').replace('-', '_')
        asset_file = key + '.png'
        asset_path = os.path.join(_cfg['ASSETS_ROOT'], asset_file)
        try:
            new_image.save(asset_path)
        except IOError:
            log.exception("Error while saving image")
            inline = True  # Retry inline version
        url = '%s%s' % (ASSETS_URL, asset_file)
    if inline:
        output = StringIO.StringIO()
        new_image.save(output, format='PNG')
        contents = output.getvalue()
        output.close()
        url = 'data:image/png;base64,' + base64.b64encode(contents)
    inline = 'url("%s")' % escape(url)
    return StringValue(inline)


def _image_color(color, width=1, height=1):
    if not Image:
        raise Exception("Images manipulation require PIL")
    c = ColorValue(color).value
    w = int(NumberValue(width).value)
    h = int(NumberValue(height).value)
    if w <= 0 or h <= 0:
        raise ValueError
    new_image = Image.new(
        mode='RGB' if c[3] == 1 else 'RGBA',
        size=(w, h),
        color=(c[0], c[1], c[2], int(c[3] * 255.0))
    )
    output = StringIO.StringIO()
    new_image.save(output, format='PNG')
    contents = output.getvalue()
    output.close()
    mime_type = 'image/png'
    url = 'data:' + mime_type + ';base64,' + base64.b64encode(contents)
    inline = 'url("%s")' % escape(url)
    return StringValue(inline)


def _sprite_map_name(map):
    """
    Returns the name of a sprite map The name is derived from the folder than
    contains the sprites.
    """
    map = StringValue(map).value
    sprite_map = sprite_maps.get(map)
    if not sprite_map:
        log.error("No sprite map found: %s", map)
    if sprite_map:
        return StringValue(sprite_map['*n*'])
    return StringValue(None)


def _sprite_file(map, sprite):
    """
    Returns the relative path (from the images directory) to the original file
    used when construction the sprite. This is suitable for passing to the
    image_width and image_height helpers.
    """
    map = StringValue(map).value
    sprite_name = StringValue(sprite).value
    sprite_map = sprite_maps.get(map)
    sprite = sprite_map and sprite_map.get(sprite_name)
    if not sprite_map:
        log.error("No sprite map found: %s", map)
    elif not sprite:
        log.error("No sprite found: %s in %s", sprite_name, sprite_map['*n*'])
    if sprite:
        return QuotedStringValue(sprite[1][0])
    return StringValue(None)


def _sprites(map):
    map = StringValue(map).value
    sprite_map = sprite_maps.get(map, {})
    return ListValue(sorted(s for s in sprite_map if not s.startswith('*')))


def _sprite(map, sprite, offset_x=None, offset_y=None):
    """
    Returns the image and background position for use in a single shorthand
    property
    """
    map = StringValue(map).value
    sprite_name = StringValue(sprite).value
    sprite_map = sprite_maps.get(map)
    sprite = sprite_map and sprite_map.get(sprite_name)
    if not sprite_map:
        log.error("No sprite map found: %s", map)
    elif not sprite:
        log.error("No sprite found: %s in %s", sprite_name, sprite_map['*n*'])
    if sprite:
        url = '%s%s?_=%s' % (ASSETS_URL, sprite_map['*f*'], sprite_map['*t*'])
        x = NumberValue(offset_x or 0, 'px')
        y = NumberValue(offset_y or 0, 'px')
        if not x or (x <= -1 or x >= 1) and x.unit != '%':
            x -= sprite[2]
        if not y or (y <= -1 or y >= 1) and y.unit != '%':
            y -= sprite[3]
        pos = "url(%s) %s %s" % (escape(url), x, y)
        return StringValue(pos)
    return StringValue('0 0')


def _sprite_url(map):
    """
    Returns a url to the sprite image.
    """
    map = StringValue(map).value
    sprite_map = sprite_maps.get(map)
    if not sprite_map:
        log.error("No sprite map found: %s", map)
    if sprite_map:
        url = '%s%s?_=%s' % (ASSETS_URL, sprite_map['*f*'], sprite_map['*t*'])
        url = "url(%s)" % escape(url)
        return StringValue(url)
    return StringValue(None)


def _sprite_position(map, sprite, offset_x=None, offset_y=None):
    """
    Returns the position for the original image in the sprite.
    This is suitable for use as a value to background-position.
    """
    map = StringValue(map).value
    sprite_name = StringValue(sprite).value
    sprite_map = sprite_maps.get(map)
    sprite = sprite_map and sprite_map.get(sprite_name)
    if not sprite_map:
        log.error("No sprite map found: %s", map)
    elif not sprite:
        log.error("No sprite found: %s in %s", sprite_name, sprite_map['*n*'])
    if sprite:
        x = None
        if offset_x is not None and not isinstance(offset_x, NumberValue):
            x = str(offset_x)
        if x not in ('left', 'right', 'center'):
            if x:
                offset_x = None
            x = NumberValue(offset_x or 0, 'px')
            if not x or (x <= -1 or x >= 1) and x.unit != '%':
                x -= sprite[2]
        y = None
        if offset_y is not None and not isinstance(offset_y, NumberValue):
            y = str(offset_y)
        if y not in ('top', 'bottom', 'center'):
            if y:
                offset_y = None
            y = NumberValue(offset_y or 0, 'px')
            if not y or (y <= -1 or y >= 1) and y.unit != '%':
                y -= sprite[3]
        pos = '%s %s' % (x, y)
        return StringValue(pos)
    return StringValue('0 0')


def _background_noise(intensity=None, opacity=None, size=None, monochrome=False, inline=False):
    if not Image:
        raise Exception("Images manipulation require PIL")

    intensity = intensity and NumberValue(intensity).value
    if not intensity or intensity < 0 or intensity > 1:
        intensity = 0.5

    opacity = opacity and NumberValue(opacity).value
    if not opacity or opacity < 0 or opacity > 1:
        opacity = 0.08

    size = size and int(NumberValue(size).value)
    if not size or size < 1 or size > 512:
        size = 200

    monochrome = bool(monochrome)

    new_image = Image.new(
        mode='RGBA',
        size=(size, size)
    )

    pixdata = new_image.load()
    for i in range(0, int(round(intensity * size ** 2))):
        x = random.randint(1, size)
        y = random.randint(1, size)
        r = random.randint(0, 255)
        a = int(round(random.randint(0, 255) * opacity))
        color = (r, r, r, a) if monochrome else (r, random.randint(0, 255), random.randint(0, 255), a)
        pixdata[x - 1, y - 1] = color

    if not inline:
        key = (intensity, opacity, size, monochrome)
        asset_file = 'noise_%s%sx%s+%s+%s' % ('mono_' if monochrome else '', size, size, to_str(intensity).replace('.', '_'), to_str(opacity).replace('.', '_'))
        asset_file = asset_file + '-' + base64.urlsafe_b64encode(hashlib.md5(repr(key)).digest()).rstrip('=').replace('-', '_')
        asset_file = asset_file + '.png'
        asset_path = os.path.join(_cfg['ASSETS_ROOT'], asset_file)
        try:
            new_image.save(asset_path)
        except IOError:
            log.exception("Error while saving image")
            inline = True  # Retry inline version
        url = '%s%s' % (ASSETS_URL, asset_file)
    if inline:
        output = StringIO.StringIO()
        new_image.save(output, format='PNG')
        contents = output.getvalue()
        output.close()
        url = 'data:image/png;base64,' + base64.b64encode(contents)

    inline = 'url("%s")' % escape(url)
    return StringValue(inline)


def _stylesheet_url(path, only_path=False, cache_buster=True):
    """
    Generates a path to an asset found relative to the project's css directory.
    Passing a true value as the second argument will cause the only the path to
    be returned instead of a `url()` function
    """
    filepath = StringValue(path).value
    if callable(_cfg['STATIC_ROOT']):
        try:
            _file, _storage = list(_cfg['STATIC_ROOT'](filepath))[0]
            d_obj = _storage.modified_time(_file)
            filetime = int(time.mktime(d_obj.timetuple()))
        except:
            filetime = 'NA'
    else:
        _path = os.path.join(_cfg['STATIC_ROOT'], filepath)
        if os.path.exists(_path):
            filetime = int(os.path.getmtime(_path))
        else:
            filetime = 'NA'
    BASE_URL = STATIC_URL

    url = '%s%s' % (BASE_URL, filepath)
    if cache_buster:
        url += '?_=%s' % filetime
    if not only_path:
        url = 'url("%s")' % (url)
    return StringValue(url)


def __font_url(path, only_path=False, cache_buster=True, inline=False):
    filepath = StringValue(path).value
    path = None
    if callable(_cfg['STATIC_ROOT']):
        try:
            _file, _storage = list(_cfg['STATIC_ROOT'](filepath))[0]
            d_obj = _storage.modified_time(_file)
            filetime = int(time.mktime(d_obj.timetuple()))
            if inline:
                path = _storage.open(_file)
        except:
            filetime = 'NA'
    else:
        _path = os.path.join(_cfg['STATIC_ROOT'], filepath)
        if os.path.exists(_path):
            filetime = int(os.path.getmtime(_path))
            if inline:
                path = open(_path, 'rb')
        else:
            filetime = 'NA'
    BASE_URL = STATIC_URL

    if path and inline:
        mime_type = mimetypes.guess_type(filepath)[0]
        url = 'data:' + mime_type + ';base64,' + base64.b64encode(path.read())
    else:
        url = '%s%s' % (BASE_URL, filepath)
        if cache_buster:
            url += '?_=%s' % filetime

    if not only_path:
        url = 'url("%s")' % escape(url)
    return StringValue(url)


def __font_files(args, inline):
    if len(args) == 1 and isinstance(args[0], (list, tuple, ListValue)):
        args = ListValue(args[0]).values()
    n = 0
    params = [[], []]
    for arg in args:
        if isinstance(arg, ListValue):
            if len(arg) == 2:
                if n % 2 == 1:
                    params[1].append(None)
                    n += 1
                params[0].append(arg[0])
                params[1].append(arg[1])
                n += 2
            else:
                for arg2 in arg:
                    params[n % 2].append(arg2)
                    n += 1
        else:
            params[n % 2].append(arg)
            n += 1
    len0 = len(params[0])
    len1 = len(params[1])
    if len1 < len0:
        params[1] += [None] * (len0 - len1)
    elif len0 < len1:
        params[0] += [None] * (len1 - len0)
    fonts = []
    for font, format in zip(params[0], params[1]):
        if format:
            fonts.append('%s format("%s")' % (__font_url(font, inline=inline), StringValue(format).value))
        else:
            fonts.append(__font_url(font, inline=inline))
    return ListValue(fonts)


def _font_url(path, only_path=False, cache_buster=True):
    """
    Generates a path to an asset found relative to the project's font directory.
    Passing a true value as the second argument will cause the only the path to
    be returned instead of a `url()` function
    """
    return __font_url(path, only_path, cache_buster, False)


def _font_files(*args):
    return __font_files(args, inline=False)


def _inline_font_files(*args):
    return __font_files(args, inline=True)


def __image_url(path, only_path=False, cache_buster=True, dst_color=None, src_color=None, inline=False, mime_type=None):
    if src_color and dst_color:
        if not Image:
            raise Exception("Images manipulation require PIL")
    filepath = StringValue(path).value
    mime_type = inline and (StringValue(mime_type).value or mimetypes.guess_type(filepath)[0])
    path = None
    if callable(_cfg['STATIC_ROOT']):
        try:
            _file, _storage = list(_cfg['STATIC_ROOT'](filepath))[0]
            d_obj = _storage.modified_time(_file)
            filetime = int(time.mktime(d_obj.timetuple()))
            if inline or dst_color:
                path = _storage.open(_file)
        except:
            filetime = 'NA'
    else:
        _path = os.path.join(_cfg['STATIC_ROOT'], filepath)
        if os.path.exists(_path):
            filetime = int(os.path.getmtime(_path))
            if inline or dst_color:
                path = open(_path, 'rb')
        else:
            filetime = 'NA'
    BASE_URL = STATIC_URL
    if path:
        src_color = src_color and tuple(int(round(c)) for c in ColorValue(src_color).value[:3]) if src_color else (0, 0, 0)
        dst_color = dst_color and [int(round(c)) for c in ColorValue(dst_color).value[:3]]

        file_name, file_ext = os.path.splitext(os.path.normpath(filepath).replace('\\', '_').replace('/', '_'))
        key = (filetime, src_color, dst_color)
        key = file_name + '-' + base64.urlsafe_b64encode(hashlib.md5(repr(key)).digest()).rstrip('=').replace('-', '_')
        asset_file = key + file_ext
        asset_path = os.path.join(_cfg['ASSETS_ROOT'], asset_file)

        if os.path.exists(asset_path):
            filepath = asset_file
            BASE_URL = ASSETS_URL
            if inline:
                path = open(asset_path, 'rb')
                url = 'data:' + mime_type + ';base64,' + base64.b64encode(path.read())
            else:
                url = '%s%s' % (BASE_URL, filepath)
                if cache_buster:
                    filetime = int(os.path.getmtime(asset_path))
                    url += '?_=%s' % filetime
        else:
            image = Image.open(path)
            image = image.convert("RGBA")
            if dst_color:
                pixdata = image.load()
                for y in xrange(image.size[1]):
                    for x in xrange(image.size[0]):
                        if pixdata[x, y][:3] == src_color:
                            new_color = tuple(dst_color + [pixdata[x, y][3]])
                            pixdata[x, y] = new_color
            if not inline:
                try:
                    image.save(asset_path)
                    filepath = asset_file
                    BASE_URL = ASSETS_URL
                    if cache_buster:
                        filetime = int(os.path.getmtime(asset_path))
                except IOError:
                    log.exception("Error while saving image")
                    inline = True  # Retry inline version
                url = '%s%s' % (ASSETS_URL, asset_file)
                if cache_buster:
                    url += '?_=%s' % filetime
            if inline:
                output = StringIO.StringIO()
                image.save(output, format='PNG')
                contents = output.getvalue()
                output.close()
                url = 'data:' + mime_type + ';base64,' + base64.b64encode(contents)
    else:
        url = '%s%s' % (BASE_URL, filepath)
        if cache_buster:
            url += '?_=%s' % filetime

    if not only_path:
        url = 'url("%s")' % escape(url)
    return StringValue(url)


def _inline_image(image, mime_type=None, dst_color=None, src_color=None):
    """
    Embeds the contents of a file directly inside your stylesheet, eliminating
    the need for another HTTP request. For small files such images or fonts,
    this can be a performance benefit at the cost of a larger generated CSS
    file.
    """
    return __image_url(image, False, False, dst_color, src_color, True, mime_type)


def _image_url(path, only_path=False, cache_buster=True, dst_color=None, src_color=None):
    """
    Generates a path to an asset found relative to the project's images
    directory.
    Passing a true value as the second argument will cause the only the path to
    be returned instead of a `url()` function
    """
    return __image_url(path, only_path, cache_buster, dst_color, src_color, False, None)


def _image_width(image):
    """
    Returns the width of the image found at the path supplied by `image`
    relative to your project's images directory.
    """
    if not Image:
        raise Exception("Images manipulation require PIL")
    file = StringValue(image).value
    path = None
    try:
        width = sprite_images[file][0]
    except KeyError:
        width = 0
        if callable(_cfg['STATIC_ROOT']):
            try:
                _file, _storage = list(_cfg['STATIC_ROOT'](file))[0]
                path = _storage.open(_file)
            except:
                pass
        else:
            _path = os.path.join(_cfg['STATIC_ROOT'], file)
            if os.path.exists(_path):
                path = open(_path, 'rb')
        if path:
            image = Image.open(path)
            size = image.size
            width = size[0]
            sprite_images[file] = size
    return NumberValue(width, 'px')


def _image_height(image):
    """
    Returns the height of the image found at the path supplied by `image`
    relative to your project's images directory.
    """
    if not Image:
        raise Exception("Images manipulation require PIL")
    file = StringValue(image).value
    path = None
    try:
        height = sprite_images[file][1]
    except KeyError:
        height = 0
        if callable(_cfg['STATIC_ROOT']):
            try:
                _file, _storage = list(_cfg['STATIC_ROOT'](file))[0]
                path = _storage.open(_file)
            except:
                pass
        else:
            _path = os.path.join(_cfg['STATIC_ROOT'], file)
            if os.path.exists(_path):
                path = open(_path, 'rb')
        if path:
            image = Image.open(path)
            size = image.size
            height = size[1]
            sprite_images[file] = size
    return NumberValue(height, 'px')


################################################################################


def __position(opposite, *p):
    pos = set()
    hrz = vrt = None
    for _p in p:
        pos.update(StringValue(_p).value.split())
    if 'left' in pos:
        hrz = 'right' if opposite else 'left'
    elif 'right' in pos:
        hrz = 'left' if opposite else 'right'
    else:
        hrz = 'center'
    if 'top' in pos:
        vrt = 'bottom' if opposite else 'top'
    elif 'bottom' in pos:
        vrt = 'top' if opposite else 'bottom'
    else:
        vrt = 'center'
    if hrz == vrt:
        vrt = None
    return ListValue(list(v for v in (hrz, vrt) if v is not None))


def _position(*p):
    return __position(False, *p)


def _opposite_position(*p):
    return __position(True, *p)


def _grad_point(*p):
    pos = set()
    hrz = vrt = NumberValue(0.5, '%')
    for _p in p:
        pos.update(StringValue(_p).value.split())
    if 'left' in pos:
        hrz = NumberValue(0, '%')
    elif 'right' in pos:
        hrz = NumberValue(1, '%')
    if 'top' in pos:
        vrt = NumberValue(0, '%')
    elif 'bottom' in pos:
        vrt = NumberValue(1, '%')
    return ListValue(list(v for v in (hrz, vrt) if v is not None))


################################################################################
# Specific to pyScss parser functions:

def _convert_to(value, type):
    return value.convert_to(type)


# Parser/functions map:
fnct = {
    'grid-image:4': _grid_image,
    'grid-image:5': _grid_image,
    'image-color:1': _image_color,
    'image-color:2': _image_color,
    'image-color:3': _image_color,
    'sprite-map:1': _sprite_map,
    'sprite-names:1': _sprites,
    'sprites:1': _sprites,
    'sprite:2': _sprite,
    'sprite:3': _sprite,
    'sprite:4': _sprite,
    'sprite-map-name:1': _sprite_map_name,
    'sprite-file:2': _sprite_file,
    'sprite-url:1': _sprite_url,
    'sprite-position:2': _sprite_position,
    'sprite-position:3': _sprite_position,
    'sprite-position:4': _sprite_position,
    'background-noise:0': _background_noise,
    'background-noise:1': _background_noise,
    'background-noise:2': _background_noise,
    'background-noise:3': _background_noise,
    'background-noise:4': _background_noise,

    'image-url:1': _image_url,
    'image-url:2': _image_url,
    'image-url:3': _image_url,
    'image-url:4': _image_url,
    'image-url:5': _image_url,
    'inline-image:1': _inline_image,
    'inline-image:2': _inline_image,
    'image-width:1': _image_width,
    'image-height:1': _image_height,

    'stylesheet-url:1': _stylesheet_url,
    'stylesheet-url:2': _stylesheet_url,

    'font-url:1': _font_url,
    'font-url:2': _font_url,

    'font-files:n': _font_files,
    'inline-font-files:n': _inline_font_files,

    'opposite-position:n': _opposite_position,
    'grad-point:n': _grad_point,
    'grad-end-position:n': _grad_end_position,
    'color-stops:n': _color_stops,
    'color-stops-in-percentages:n': _color_stops_in_percentages,
    'grad-color-stops:n': _grad_color_stops,
    'radial-gradient:n': _radial_gradient,
    'linear-gradient:n': _linear_gradient,
    'radial-svg-gradient:n': _radial_svg_gradient,
    'linear-svg-gradient:n': _linear_svg_gradient,

    'fadein:2': _opacify, #spelling
    'fadeout:2': _transparentize, #spelling
    'greyscale:1': _grayscale, #spelling

    'adjust-lightness:2': _adjust_lightness,
    'adjust-saturation:2': _adjust_saturation,
    'scale-lightness:2': _scale_lightness,
    'scale-saturation:2': _scale_saturation,
    'spin:2': _adjust_hue,
    'hsl:1': _hsl2,
    'hsla:1': _hsla2,
    'hsla:2': _hsla2,
    'rgb:1': _rgb2,
    'rgba:1': _rgba2,
    'ie-hex-str:1': _ie_hex_str,


    'prefixed:n': _prefixed,
    'prefix:n': _prefix,
    '-moz:n': __moz,
    '-svg:n': __svg,
    '-css2:n': __css2,
    '-pie:n': __pie,
    '-webkit:n': __webkit,
    '-owg:n': __owg,
    '-ms:n': __ms,
    '-o:n': __o,

    '-compass-list:n': __compass_list,
    '-compass-space-list:n': __compass_space_list,
    'blank:n': _blank,
    'compact:n': _compact,
    'reject:n': _reject,
    '-compass-slice:3': __compass_slice,
    'max:n': _max,
    'min:n': _min,
    '-compass-nth:2': _nth,
    'first-value-of:n': _first_value_of,
    '-compass-list-size:n': _length,
    'append:2': _append,
    'append:3': _append,

    'nest:n': _nest,
    'append-selector:2': _append_selector,
    'headers:0': _headers,
    'headers:1': _headers,
    'headers:2': _headers,
    'headings:0': _headers,
    'headings:1': _headers,
    'headings:2': _headers,
    'enumerate:3': _enumerate,
    'enumerate:4': _enumerate,
    'range:1': _range,
    'range:2': _range,

    'if:2': _if,
    'elements-of-type:1': _elements_of_type,
    'escape:1': _unquote,
    'e:1': _unquote,

    'sin:1': Value._wrap(math.sin),
    'cos:1': Value._wrap(math.cos),
    'tan:1': Value._wrap(math.tan),
    'abs:1': Value._wrap(abs),
    'pi:0': _pi,
}

for u in _units:
    fnct[u + ':2'] = _convert_to

fnct.update(func_mapping)
