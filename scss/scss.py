# -*- coding: utf-8 -*-

from collections import deque
import glob
import os
import re
import textwrap

from .colors import _colors, _short_color_re, _reverse_colors
from .config import (_cfg, _default_scss_files, _default_scss_index,
                     _default_scss_opts, _default_scss_vars, log)
from .data_types import BooleanValue, NumberValue, ListValue, StringValue
from .functions import _sprite_map
from .grammar import CalculatorScanner, eval_expr, interpolate
from .parser import locate_blocks
from .regexes import (SEPARATOR, _collapse_properties_space_re, _colors_re,
                      _expand_rules_space_re, _interpolate_re, _ml_comment_re,
                      _nl_num_nl_re, _nl_re, _prop_split_re, _sl_comment_re,
                      _spaces_re, _strings_re, _variable_re, _escape_chars_re,
                      _skip_word_re, _skip_re, _expr_glob_re,
                      _reverse_colors_re, _zero_units_re, _zero_re)
from .support import (SELECTORS, MEDIA, POSITION, CODESTR, OPTIONS, CONTEXT,
                      PROPERTIES, INDEX, LINENO, PATH, DEPS, FILEID,
                      print_timing, spawn_rule, _reverse_safe_strings,
                      _reverse_safe_strings_re, _safe_strings,
                      _safe_strings_re)
from .utils import depar, dequote, split_params, to_str


class Scss(object):
    # configuration:
    construct = 'self'

    def __init__(self, scss_vars=None, scss_opts=None, scss_files=None):
        self._scss_vars = scss_vars
        self._scss_opts = scss_opts
        self._scss_files = scss_files
        self.reset()

    def clean(self):
        self.children = deque()
        self.rules = []
        self._rules = {}
        self.parts = {}

    def reset(self, input_scss=None):
        if hasattr(CalculatorScanner, 'cleanup'):
            CalculatorScanner.cleanup()

        # Initialize
        self.css_files = []

        self.scss_vars = _default_scss_vars.copy()
        if self._scss_vars is not None:
            self.scss_vars.update(self._scss_vars)

        self.scss_opts = _default_scss_opts.copy()
        if self._scss_opts is not None:
            self.scss_opts.update(self._scss_opts)

        self.scss_files = {}
        self._scss_files_order = []
        for f, c in _default_scss_files.iteritems():
            if f not in self.scss_files:
                self._scss_files_order.append(f)
            self.scss_files[f] = c
        if self._scss_files is not None:
            for f, c in self._scss_files.iteritems():
                if f not in self.scss_files:
                    self._scss_files_order.append(f)
                self.scss_files[f] = c

        self._scss_index = _default_scss_index.copy()

        self._contexts = {}
        self._replaces = {}

        self.clean()

    @print_timing(2)
    def Compilation(self, input_scss=None):
        if input_scss is not None:
            self._scss_files = {'<string>': input_scss}

        self.reset()

        # Compile
        for fileid in self._scss_files_order:
            codestr = self.scss_files[fileid]
            codestr = self.load_string(codestr, fileid)
            self.scss_files[fileid] = codestr
            rule = spawn_rule(fileid=fileid, codestr=codestr, context=self.scss_vars, options=self.scss_opts, index=self._scss_index)
            self.children.append(rule)

        # this will manage rule: child objects inside of a node
        self.parse_children()

        # this will manage rule: ' extends '
        self.parse_extends()

        # this will manage the order of the rules
        self.manage_order()

        self.parse_properties()

        final_cont = ''
        for fileid in self.css_files:
            if fileid != '<string>':
                final_cont += '/* Generated from: ' + fileid + ' */\n'
            fcont = self.create_css(fileid)
            final_cont += fcont

        final_cont = self.post_process(final_cont)

        return final_cont
    compile = Compilation

    def load_string(self, codestr, filename=None):
        if filename is not None:
            codestr += '\n'

            idx = {
                'next_id': len(self._scss_index),
                'line': 1,
            }

            def _cnt(m):
                idx['line'] += 1
                lineno = '%s:%d' % (filename, idx['line'])
                next_id = idx['next_id']
                self._scss_index[next_id] = lineno
                idx['next_id'] += 1
                return '\n' + str(next_id) + SEPARATOR
            lineno = '%s:%d' % (filename, idx['line'])
            next_id = idx['next_id']
            self._scss_index[next_id] = lineno
            codestr = str(next_id) + SEPARATOR + _nl_re.sub(_cnt, codestr)

        # remove empty lines
        codestr = _nl_num_nl_re.sub('\n', codestr)

        # protects codestr: "..." strings
        codestr = _strings_re.sub(lambda m: _reverse_safe_strings_re.sub(lambda n: _reverse_safe_strings[n.group(0)], m.group(0)), codestr)

        # removes multiple line comments
        codestr = _ml_comment_re.sub('', codestr)

        # removes inline comments, but not :// (protocol)
        codestr = _sl_comment_re.sub('', codestr)

        codestr = _safe_strings_re.sub(lambda m: _safe_strings[m.group(0)], codestr)

        # expand the space in rules
        codestr = _expand_rules_space_re.sub(' {', codestr)

        # collapse the space in properties blocks
        codestr = _collapse_properties_space_re.sub(r'\1{', codestr)

        # to do math operations, we need to get the color's hex values (for color names):
        def _pp(m):
            v = m.group(0)
            return _colors.get(v, v)
        codestr = _colors_re.sub(_pp, codestr)

        return codestr

    def longest_common_prefix(self, seq1, seq2):
        start = 0
        common = 0
        length = min(len(seq1), len(seq2))
        while start < length:
            if seq1[start] != seq2[start]:
                break
            if seq1[start] == ' ':
                common = start + 1
            elif seq1[start] in ('#', ':', '.'):
                common = start
            start += 1
        return common

    def longest_common_suffix(self, seq1, seq2):
        seq1, seq2 = seq1[::-1], seq2[::-1]
        start = 0
        common = 0
        length = min(len(seq1), len(seq2))
        while start < length:
            if seq1[start] != seq2[start]:
                break
            if seq1[start] == ' ':
                common = start + 1
            elif seq1[start] in ('#', ':', '.'):
                common = start + 1
            start += 1
        return common

    def normalize_selectors(self, _selectors, extra_selectors=None, extra_parents=None):
        """
        Normalizes or extends selectors in a string.
        An optional extra parameter that can be a list of extra selectors to be
        added to the final normalized selectors string.
        """
        # Fixe tabs and spaces in selectors
        _selectors = _spaces_re.sub(' ', _selectors)

        if isinstance(extra_selectors, basestring):
            extra_selectors = extra_selectors.split(',')

        if isinstance(extra_parents, basestring):
            extra_parents = extra_parents.split('&')

        parents = set()
        if ' extends ' in _selectors:
            selectors = set()
            for key in _selectors.split(','):
                child, _, parent = key.partition(' extends ')
                child = child.strip()
                parent = parent.strip()
                selectors.add(child)
                parents.update(s.strip() for s in parent.split('&') if s.strip())
        else:
            selectors = set(s.strip() for s in _selectors.split(',') if s.strip())
        if extra_selectors:
            selectors.update(s.strip() for s in extra_selectors if s.strip())
        selectors.discard('')
        if not selectors:
            return ''
        if extra_parents:
            parents.update(s.strip() for s in extra_parents if s.strip())
        parents.discard('')
        if parents:
            return ','.join(sorted(selectors)) + ' extends ' + '&'.join(sorted(parents))
        return ','.join(sorted(selectors))

    def apply_vars(self, cont, context, options=None, rule=None, _dequote=False):
        if isinstance(cont, basestring) and '$' in cont:
            if cont in context:
                # Optimization: the full cont is a variable in the context,
                # flatten the interpolation and use it:
                while isinstance(cont, basestring) and cont in context:
                    _cont = context[cont]
                    if _cont == cont:
                        break
                    cont = _cont
            else:
                # Flatten the context (no variables mapping to variables)
                flat_context = {}
                for k, v in context.items():
                    while isinstance(v, basestring) and v in context:
                        _v = context[v]
                        if _v == v:
                            break
                        v = _v
                    flat_context[k] = v

                # Interpolate variables:
                def _av(m):
                    v = flat_context.get(m.group(2))
                    if v:
                        v = to_str(v)
                        if _dequote and m.group(1):
                            v = dequote(v)
                    elif v is not None:
                        v = to_str(v)
                    else:
                        v = m.group(0)
                    return v

                cont = _interpolate_re.sub(_av, cont)
        if options is not None:
            # ...apply math:
            cont = self.do_glob_math(cont, context, options, rule, _dequote)
        return cont

    @print_timing(3)
    def parse_children(self):
        pos = 0
        while True:
            try:
                rule = self.children.popleft()
            except:
                break
            # Check if the block has nested blocks and work it out:
            _selectors, _, _parents = rule[SELECTORS].partition(' extends ')
            _selectors = _selectors.split(',')
            _parents = set(_parents.split('&'))
            _parents.discard('')

            # manage children or expand children:
            _children = deque()
            self.manage_children(rule, _selectors, _parents, _children, None, rule[MEDIA])
            self.children.extendleft(_children)

            # prepare maps:
            if _parents:
                rule[SELECTORS] = ','.join(_selectors) + ' extends ' + '&'.join(_parents)
            rule[POSITION] = pos
            selectors = rule[SELECTORS]
            self.parts.setdefault(selectors, [])
            self.parts[selectors].append(rule)
            self.rules.append(rule)
            pos += 1

            #print >>sys.stderr, '='*80
            #for r in [rule]+list(self.children)[:5]: print >>sys.stderr, repr(r[POSITION]), repr(r[SELECTORS]), repr(r[CODESTR][:80]+('...' if len(r[CODESTR])>80 else ''))
            #for r in [rule]+list(self.children)[:5]: print >>sys.stderr, repr(r[POSITION]), repr(r[SELECTORS]), repr(r[CODESTR][:80]+('...' if len(r[CODESTR])>80 else '')), dict((k, v) for k, v in r[CONTEXT].items() if k.startswith('$') and not k.startswith('$__')), dict(r[PROPERTIES]).keys()

    @print_timing(4)
    def manage_children(self, rule, p_selectors, p_parents, p_children, scope, media):
        for c_lineno, c_property, c_codestr in locate_blocks(rule[CODESTR]):
            if '@return' in rule[OPTIONS]:
                return
            # Rules preprocessing...
            if c_property.startswith('+'):  # expands a '+' at the beginning of a rule as @include
                c_property = '@include ' + c_property[1:]
                try:
                    if '(' not in c_property or c_property.index(':') < c_property.index('('):
                        c_property = c_property.replace(':', '(', 1)
                        if '(' in c_property:
                            c_property += ')'
                except ValueError:
                    pass
            elif c_property.startswith('='):  # expands a '=' at the beginning of a rule as @mixin
                c_property = '@mixin' + c_property[1:]
            elif c_property == '@prototype ':  # Remove '@prototype '
                c_property = c_property[11:]
            ####################################################################
            if c_property.startswith('@'):
                code, name = (c_property.split(None, 1) + [''])[:2]
                code = code.lower()
                if code == '@warn':
                    name = self.calculate(name, rule[CONTEXT], rule[OPTIONS], rule)
                    log.warn(dequote(to_str(name)))
                elif code == '@print':
                    name = self.calculate(name, rule[CONTEXT], rule[OPTIONS], rule)
                    log.info(dequote(to_str(name)))
                elif code == '@raw':
                    name = self.calculate(name, rule[CONTEXT], rule[OPTIONS], rule)
                    log.info(repr(name))
                elif code == '@debug':
                    global DEBUG
                    name = name.strip()
                    if name.lower() in ('1', 'true', 't', 'yes', 'y', 'on'):
                        name = 1
                    elif name.lower() in ('0', 'false', 'f', 'no', 'n', 'off', 'undefined'):
                        name = 0
                    DEBUG = name
                    log.info("Debug mode is %s", 'On' if DEBUG else 'Off')
                elif code == '@option':
                    self._settle_options(rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name)
                elif code == '@content':
                    self._do_content(rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name)
                elif code == '@import':
                    self._do_import(rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name)
                elif code == '@extend':
                    name = self.apply_vars(name, rule[CONTEXT], rule[OPTIONS], rule)
                    p_parents.update(p.strip() for p in name.replace(',', '&').split('&'))
                    p_parents.discard('')
                elif c_codestr is not None and code in ('@mixin', '@function'):
                    self._do_functions(rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name)
                elif code == '@return':
                    ret = self.calculate(name, rule[CONTEXT], rule[OPTIONS], rule)
                    rule[OPTIONS]['@return'] = ret
                elif code == '@include':
                    self._do_include(rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name)
                elif c_codestr is not None and (code == '@if' or c_property.startswith('@else if ')):
                    self._do_if(rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name)
                elif c_codestr is not None and code == '@else':
                    self._do_else(rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name)
                elif c_codestr is not None and code == '@for':
                    self._do_for(rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name)
                elif c_codestr is not None and code == '@each':
                    self._do_each(rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name)
                # elif c_codestr is not None and code == '@while':
                #     self._do_while(rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name)
                elif c_codestr is not None and code in ('@variables', '@vars'):
                    self._get_variables(rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr)
                elif c_codestr is not None and code == '@media':
                    _media = (media or []) + [name]
                    rule[CODESTR] = self.construct + ' {' + c_codestr + '}'
                    self.manage_children(rule, p_selectors, p_parents, p_children, scope, _media)
                elif c_codestr is None:
                    rule[PROPERTIES].append((c_lineno, c_property, None))
                elif scope is None:  # needs to have no scope to crawl down the nested rules
                    self._nest_rules(rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr)
            ####################################################################
            # Properties
            elif c_codestr is None:
                self._get_properties(rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr)
            # Nested properties
            elif c_property.endswith(':'):
                rule[CODESTR] = c_codestr
                self.manage_children(rule, p_selectors, p_parents, p_children, (scope or '') + c_property[:-1] + '-', media)
            ####################################################################
            # Nested rules
            elif scope is None:  # needs to have no scope to crawl down the nested rules
                self._nest_rules(rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr)

    @print_timing(10)
    def _settle_options(self, rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name):
        for option in name.split(','):
            option, value = (option.split(':', 1) + [''])[:2]
            option = option.strip().lower()
            value = value.strip()
            if option:
                if value.lower() in ('1', 'true', 't', 'yes', 'y', 'on'):
                    value = 1
                elif value.lower() in ('0', 'false', 'f', 'no', 'n', 'off', 'undefined'):
                    value = 0
                rule[OPTIONS][option] = value

    @print_timing(10)
    def _do_functions(self, rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name):
        """
        Implements @mixin and @function
        """
        if name:
            funct, params, _ = name.partition('(')
            funct = funct.strip()
            params = split_params(depar(params + _))
            defaults = {}
            new_params = []
            for param in params:
                param, _, default = param.partition(':')
                param = param.strip()
                default = default.strip()
                if param:
                    new_params.append(param)
                    if default:
                        default = self.apply_vars(default, rule[CONTEXT], None, rule)
                        defaults[param] = default
            context = rule[CONTEXT].copy()
            for p in new_params:
                context.pop(p, None)
            mixin = [list(new_params), defaults, self.apply_vars(c_codestr, context, None, rule)]
            if code == '@function':
                def _call(mixin):
                    def __call(R, *args, **kwargs):
                        m_params = mixin[0]
                        m_vars = rule[CONTEXT].copy()
                        m_vars.update(mixin[1])
                        m_codestr = mixin[2]
                        for i, a in enumerate(args):
                            m_vars[m_params[i]] = a
                        m_vars.update(kwargs)
                        _options = rule[OPTIONS].copy()
                        _rule = spawn_rule(R, codestr=m_codestr, context=m_vars, options=_options, deps=set(), properties=[], final=False, lineno=c_lineno)
                        self.manage_children(_rule, p_selectors, p_parents, p_children, (scope or '') + '', R[MEDIA])
                        ret = _rule[OPTIONS].pop('@return', '')
                        return ret
                    return __call
                _mixin = _call(mixin)
                _mixin.mixin = mixin
                mixin = _mixin
            # Insert as many @mixin options as the default parameters:
            while len(new_params):
                rule[OPTIONS]['%s %s:%d' % (code, funct, len(new_params))] = mixin
                param = new_params.pop()
                if param not in defaults:
                    break
            if not new_params:
                rule[OPTIONS][code + ' ' + funct + ':0'] = mixin

    @print_timing(10)
    def _do_include(self, rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name):
        """
        Implements @include, for @mixins
        """
        funct, params, _ = name.partition('(')
        funct = funct.strip()
        funct = self.do_glob_math(funct, rule[CONTEXT], rule[OPTIONS], rule, True)
        params = split_params(depar(params + _))
        new_params = {}
        num_args = 0
        for param in params:
            varname, _, param = param.partition(':')
            if param:
                param = param.strip()
                varname = varname.strip()
            else:
                param = varname.strip()
                varname = num_args
                if param:
                    num_args += 1
            if param:
                new_params[varname] = param
        mixin = rule[OPTIONS].get('@mixin %s:%s' % (funct, num_args))
        if not mixin:
            # Fallback to single parmeter:
            mixin = rule[OPTIONS].get('@mixin %s:1' % (funct,))
            if mixin and all(map(lambda o: isinstance(o, int), new_params.keys())):
                new_params = {0: ', '.join(new_params.values())}
        if mixin:
            m_params = mixin[0]
            m_vars = mixin[1].copy()
            m_codestr = mixin[2]
            for varname, value in new_params.items():
                try:
                    m_param = m_params[varname]
                except:
                    m_param = varname
                value = self.calculate(value, rule[CONTEXT], rule[OPTIONS], rule)
                m_vars[m_param] = value
            for p in m_vars:
                if p not in new_params:
                    if isinstance(m_vars[p], basestring):
                        value = self.calculate(m_vars[p], m_vars, rule[OPTIONS], rule)
                        m_vars[p] = value
            _context = rule[CONTEXT].copy()
            _context.update(m_vars)
            _rule = spawn_rule(rule, codestr=m_codestr, context=_context, lineno=c_lineno)
            _rule[OPTIONS]['@content'] = c_codestr
            self.manage_children(_rule, p_selectors, p_parents, p_children, scope, media)
        else:
            log.error("Required mixin not found: %s:%d (%s)", funct, num_args, rule[INDEX][rule[LINENO]])

    @print_timing(10)
    def _do_content(self, rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name):
        """
        Implements @content
        """
        if '@content' not in rule[OPTIONS]:
            log.error("Content string not found for @content (%s)", rule[INDEX][rule[LINENO]])
        c_codestr = rule[OPTIONS].pop('@content', '')
        rule[CODESTR] = c_codestr
        self.manage_children(rule, p_selectors, p_parents, p_children, scope, media)

    @print_timing(10)
    def _do_import(self, rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name):
        """
        Implements @import
        Load and import mixins and functions and rules
        """
        i_codestr = None
        if '..' not in name and '://' not in name and 'url(' not in name:  # Protect against going to prohibited places...
            names = name.split(',')
            for name in names:
                name = dequote(name.strip())
                if '@import ' + name not in rule[OPTIONS]:  # If already imported in this scope, skip...
                    unsupported = []
                    load_paths = []
                    try:
                        raise KeyError
                        i_codestr = self.scss_files[name]
                    except KeyError:
                        filename = os.path.basename(name)
                        dirname = os.path.dirname(name)
                        i_codestr = None

                        # TODO: Convert global LOAD_PATHS to a list. Use it directly.
                        # Doing the above will break backwards compatibility!
                        if hasattr(_cfg['LOAD_PATHS'], 'split'):
                            load_path_list = _cfg['LOAD_PATHS'].split(',') # Old style
                        else:
                            load_path_list = _cfg['LOAD_PATHS'] # New style

                        for path in [ './' ] + load_path_list:
                            for basepath in [ './', os.path.dirname(rule[PATH]) ]:
                                i_codestr = None
                                full_path = os.path.realpath(os.path.join(path, basepath, dirname))
                                if full_path not in load_paths:
                                    try:
                                        full_filename = os.path.join(full_path, '_' + filename)
                                        i_codestr = open(full_filename + '.scss').read()
                                    except IOError:
                                        if os.path.exists(full_filename + '.sass'):
                                            unsupported.append(full_filename + '.sass')
                                        try:
                                            full_filename = os.path.join(full_path, filename)
                                            i_codestr = open(full_filename + '.scss').read()
                                        except IOError:
                                            if os.path.exists(full_filename + '.sass'):
                                                unsupported.append(full_filename + '.sass')
                                            try:
                                                full_filename = os.path.join(full_path, '_' + filename)
                                                i_codestr = open(full_filename).read()
                                            except IOError:
                                                try:
                                                    full_filename = os.path.join(full_path, filename)
                                                    i_codestr = open(full_filename).read()
                                                except IOError:
                                                    pass
                                    if i_codestr is not None:
                                        break
                                    else:
                                        load_paths.append(full_path)
                            if i_codestr is not None:
                                break
                        if i_codestr is None:
                            i_codestr = self._do_magic_import(rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name)
                        i_codestr = self.scss_files[name] = i_codestr and self.load_string(i_codestr, full_filename)
                        if name not in self.scss_files:
                            self._scss_files_order.append(name)
                    if i_codestr is None:
                        load_paths = load_paths and "\nLoad paths:\n\t%s" % "\n\t".join(load_paths) or ''
                        unsupported = unsupported and "\nPossible matches (for unsupported file format SASS):\n\t%s" % "\n\t".join(unsupported) or ''
                        log.warn("File to import not found or unreadable: '%s' (%s)%s%s", filename, rule[INDEX][rule[LINENO]], load_paths, unsupported)
                    else:
                        _rule = spawn_rule(rule, codestr=i_codestr, path=full_filename, lineno=c_lineno)
                        self.manage_children(_rule, p_selectors, p_parents, p_children, scope, media)
                        rule[OPTIONS]['@import ' + name] = True
        else:
            rule[PROPERTIES].append((c_lineno, c_property, None))

    @print_timing(10)
    def _do_magic_import(self, rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name):
        """
        Implements @import for sprite-maps
        Imports magic sprite map directories
        """
        if callable(_cfg['STATIC_ROOT']):
            files = sorted(_cfg['STATIC_ROOT'](name))
        else:
            glob_path = os.path.join(_cfg['STATIC_ROOT'], name)
            files = glob.glob(glob_path)
            files = sorted((file[len(_cfg['STATIC_ROOT']):], None) for file in files)

        if files:
            # Build magic context
            map_name = os.path.normpath(os.path.dirname(name)).replace('\\', '_').replace('/', '_')
            kwargs = {}

            def setdefault(var, val):
                _var = '$' + map_name + '-' + var
                if _var in rule[CONTEXT]:
                    kwargs[var] = interpolate(rule[CONTEXT][_var], rule)
                else:
                    rule[CONTEXT][_var] = val
                    kwargs[var] = interpolate(val, rule)
                return rule[CONTEXT][_var]

            setdefault('sprite-base-class', StringValue('.' + map_name + '-sprite'))
            setdefault('sprite-dimensions', BooleanValue(False))
            position = setdefault('position', NumberValue(0, '%'))
            spacing = setdefault('spacing', NumberValue(0))
            repeat = setdefault('repeat', StringValue('no-repeat'))
            names = tuple(os.path.splitext(os.path.basename(file))[0] for file, storage in files)
            for n in names:
                setdefault(n + '-position', position)
                setdefault(n + '-spacing', spacing)
                setdefault(n + '-repeat', repeat)
            sprite_map = _sprite_map(name, **kwargs)
            rule[CONTEXT]['$' + map_name + '-' + 'sprites'] = sprite_map
            ret = '''
                @import "compass/utilities/sprites/base";

                // All sprites should extend this class
                // The %(map_name)s-sprite mixin will do so for you.
                #{$%(map_name)s-sprite-base-class} {
                    background: $%(map_name)s-sprites;
                }

                // Use this to set the dimensions of an element
                // based on the size of the original image.
                @mixin %(map_name)s-sprite-dimensions($name) {
                    @include sprite-dimensions($%(map_name)s-sprites, $name);
                }

                // Move the background position to display the sprite.
                @mixin %(map_name)s-sprite-position($name, $offset-x: 0, $offset-y: 0) {
                    @include sprite-position($%(map_name)s-sprites, $name, $offset-x, $offset-y);
                }

                // Extends the sprite base class and set the background position for the desired sprite.
                // It will also apply the image dimensions if $dimensions is true.
                @mixin %(map_name)s-sprite($name, $dimensions: $%(map_name)s-sprite-dimensions, $offset-x: 0, $offset-y: 0) {
                    @extend #{$%(map_name)s-sprite-base-class};
                    @include sprite($%(map_name)s-sprites, $name, $dimensions, $offset-x, $offset-y);
                }

                @mixin %(map_name)s-sprites($sprite-names, $dimensions: $%(map_name)s-sprite-dimensions) {
                    @include sprites($%(map_name)s-sprites, $sprite-names, $%(map_name)s-sprite-base-class, $dimensions);
                }

                // Generates a class for each sprited image.
                @mixin all-%(map_name)s-sprites($dimensions: $%(map_name)s-sprite-dimensions) {
                    @include %(map_name)s-sprites(%(sprites)s, $dimensions);
                }
            ''' % {'map_name': map_name, 'sprites': ' '.join(names)}
            return ret

    @print_timing(10)
    def _do_if(self, rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name):
        """
        Implements @if and @else if
        """
        if code != '@if':
            if '@if' not in rule[OPTIONS]:
                log.error("@else with no @if (%s)", rule[INDEX][rule[LINENO]])
            val = not rule[OPTIONS].get('@if', True)
            name = c_property[9:].strip()
        else:
            val = True
        if val:
            val = self.calculate(name, rule[CONTEXT], rule[OPTIONS], rule)
            val = bool(False if not val or isinstance(val, basestring) and (val in ('0', 'false', 'undefined') or _variable_re.match(val)) else val)
            if val:
                rule[CODESTR] = c_codestr
                self.manage_children(rule, p_selectors, p_parents, p_children, scope, media)
            rule[OPTIONS]['@if'] = val

    @print_timing(10)
    def _do_else(self, rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name):
        """
        Implements @else
        """
        if '@if' not in rule[OPTIONS]:
            log.error("@else with no @if (%s)", rule[INDEX][rule[LINENO]])
        val = rule[OPTIONS].pop('@if', True)
        if not val:
            rule[CODESTR] = c_codestr
            self.manage_children(rule, p_selectors, p_parents, p_children, scope, media)

    @print_timing(10)
    def _do_for(self, rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name):
        """
        Implements @for
        """
        var, _, name = name.partition('from')
        frm, _, through = name.partition('through')
        if not through:
            frm, _, through = frm.partition('to')
        frm = self.calculate(frm, rule[CONTEXT], rule[OPTIONS], rule)
        through = self.calculate(through, rule[CONTEXT], rule[OPTIONS], rule)
        try:
            frm = int(float(frm))
            through = int(float(through))
        except ValueError:
            pass
        else:
            if frm > through:
                frm, through = through, frm
                rev = reversed
            else:
                rev = lambda x: x
            var = var.strip()
            var = self.do_glob_math(var, rule[CONTEXT], rule[OPTIONS], rule, True)

            for i in rev(range(frm, through + 1)):
                rule[CODESTR] = c_codestr
                rule[CONTEXT][var] = str(i)
                self.manage_children(rule, p_selectors, p_parents, p_children, scope, media)

    @print_timing(10)
    def _do_each(self, rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name):
        """
        Implements @each
        """
        var, _, name = name.partition('in')
        name = self.calculate(name, rule[CONTEXT], rule[OPTIONS], rule)
        if name:
            name = ListValue(name)
            var = var.strip()
            var = self.do_glob_math(var, rule[CONTEXT], rule[OPTIONS], rule, True)

            for n, v in name.items():
                v = to_str(v)
                rule[CODESTR] = c_codestr
                rule[CONTEXT][var] = v
                if not isinstance(n, int):
                    rule[CONTEXT][n] = v
                self.manage_children(rule, p_selectors, p_parents, p_children, scope, media)

    # @print_timing(10)
    # def _do_while(self, rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr, code, name):
    #     THIS DOES NOT WORK AS MODIFICATION OF INNER VARIABLES ARE NOT KNOWN AT THIS POINT!!
    #     """
    #     Implements @while
    #     """
    #     first_val = None
    #     while True:
    #         val = self.calculate(name, rule[CONTEXT], rule[OPTIONS], rule)
    #         val = bool(False if not val or isinstance(val, basestring) and (val in ('0', 'false', 'undefined') or _variable_re.match(val)) else val)
    #         if first_val is None:
    #             first_val = val
    #         if not val:
    #             break
    #         rule[CODESTR] = c_codestr
    #         self.manage_children(rule, p_selectors, p_parents, p_children, scope, media)
    #     rule[OPTIONS]['@if'] = first_val

    @print_timing(10)
    def _get_variables(self, rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr):
        """
        Implements @variables and @vars
        """
        _rule = list(rule)
        _rule[CODESTR] = c_codestr
        _rule[PROPERTIES] = rule[CONTEXT]
        self.manage_children(_rule, p_selectors, p_parents, p_children, scope, media)

    @print_timing(10)
    def _get_properties(self, rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr):
        """
        Implements properties and variables extraction
        """
        prop, value = (_prop_split_re.split(c_property, 1) + [None])[:2]
        try:
            is_var = (c_property[len(prop)] == '=')
        except IndexError:
            is_var = False
        prop = prop.strip()
        prop = self.do_glob_math(prop, rule[CONTEXT], rule[OPTIONS], rule, True)
        if prop:
            if value:
                value = value.strip()
                value = self.calculate(value, rule[CONTEXT], rule[OPTIONS], rule)
            _prop = (scope or '') + prop
            if is_var or prop.startswith('$') and value is not None:
                if isinstance(value, basestring):
                    if '!default' in value:
                        if _prop in rule[CONTEXT]:
                            value = None
                        else:
                            value = value.replace('!default', '').replace('  ', ' ').strip()
                elif isinstance(value, ListValue):
                    value = ListValue(value)
                    for k, v in value.value.items():
                        if v == '!default':
                            if _prop in rule[CONTEXT]:
                                value = None
                            else:
                                del value.value[k]
                                value = value.first() if len(value) == 1 else value
                            break
                if value is not None:
                    rule[CONTEXT][_prop] = value
            else:
                _prop = self.apply_vars(_prop, rule[CONTEXT], rule[OPTIONS], rule, True)
                rule[PROPERTIES].append((c_lineno, _prop, to_str(value) if value is not None else None))

    @print_timing(10)
    def _nest_rules(self, rule, p_selectors, p_parents, p_children, scope, media, c_lineno, c_property, c_codestr):
        """
        Implements Nested CSS rules
        """
        if c_property == self.construct and rule[MEDIA] == media:
            rule[CODESTR] = c_codestr
            self.manage_children(rule, p_selectors, p_parents, p_children, scope, media)
        else:
            c_property = self.apply_vars(c_property, rule[CONTEXT], rule[OPTIONS], rule, True)

            c_selectors = self.normalize_selectors(c_property)
            c_selectors, _, c_parents = c_selectors.partition(' extends ')

            better_selectors = set()
            c_selectors = c_selectors.split(',')
            for c_selector in c_selectors:
                for p_selector in p_selectors:
                    if c_selector == self.construct:
                        better_selectors.add(p_selector)
                    elif '&' in c_selector:  # Parent References
                        better_selectors.add(c_selector.replace('&', p_selector))
                    elif p_selector:
                        better_selectors.add(p_selector + ' ' + c_selector)
                    else:
                        better_selectors.add(c_selector)
            better_selectors = ','.join(sorted(better_selectors))

            if c_parents:
                parents = set(p.strip() for p in c_parents.split('&'))
                parents.discard('')
                if parents:
                    better_selectors += ' extends ' + '&'.join(sorted(parents))

            _rule = spawn_rule(rule, codestr=c_codestr, deps=set(), context=rule[CONTEXT].copy(), options=rule[OPTIONS].copy(), selectors=better_selectors, properties=[], final=False, media=media, lineno=c_lineno)

            p_children.appendleft(_rule)

    @print_timing(4)
    def link_with_parents(self, parent, c_selectors, c_rules):
        """
        Link with a parent for the current child rule.
        If parents found, returns a list of parent rules to the child
        """
        parent_found = None
        for p_selectors, p_rules in self.parts.items():
            _p_selectors, _, _ = p_selectors.partition(' extends ')
            _p_selectors = _p_selectors.split(',')

            new_selectors = set()
            found = False

            # Finds all the parent selectors and parent selectors with another
            # bind selectors behind. For example, if `.specialClass extends .baseClass`,
            # and there is a `.baseClass` selector, the extension should create
            # `.specialClass` for that rule, but if there's also a `.baseClass a`
            # it also should create `.specialClass a`
            for p_selector in _p_selectors:
                if parent in p_selector:
                    # get the new child selector to add (same as the parent selector but with the child name)
                    # since selectors can be together, separated with # or . (i.e. something.parent) check that too:
                    for c_selector in c_selectors.split(','):
                        # Get whatever is different between the two selectors:
                        _c_selector, _parent = c_selector, parent
                        lcp = self.longest_common_prefix(_c_selector, _parent)
                        if lcp:
                            _c_selector = _c_selector[lcp:]
                            _parent = _parent[lcp:]
                        lcs = self.longest_common_suffix(_c_selector, _parent)
                        if lcs:
                            _c_selector = _c_selector[:-lcs]
                            _parent = _parent[:-lcs]
                        if _c_selector and _parent:
                            # Get the new selectors:
                            prev_symbol = '(?<![%#.:])' if _parent[0] in ('%', '#', '.', ':') else r'(?<![-\w%#.:])'
                            post_symbol = r'(?![-\w])'
                            new_parent = re.sub(prev_symbol + _parent + post_symbol, _c_selector, p_selector)
                            if p_selector != new_parent:
                                new_selectors.add(new_parent)
                                found = True

            if found:
                # add parent:
                parent_found = parent_found or []
                parent_found.extend(p_rules)

            if new_selectors:
                new_selectors = self.normalize_selectors(p_selectors, new_selectors)
                # rename node:
                if new_selectors != p_selectors:
                    del self.parts[p_selectors]
                    self.parts.setdefault(new_selectors, [])
                    self.parts[new_selectors].extend(p_rules)

                deps = set()
                # save child dependencies:
                for c_rule in c_rules or []:
                    c_rule[SELECTORS] = c_selectors  # re-set the SELECTORS for the rules
                    deps.add(c_rule[POSITION])

                for p_rule in p_rules:
                    p_rule[SELECTORS] = new_selectors  # re-set the SELECTORS for the rules
                    p_rule[DEPS].update(deps)  # position is the "index" of the object

        return parent_found

    @print_timing(3)
    def parse_extends(self):
        """
        For each part, create the inheritance parts from the ' extends '
        """
        # To be able to manage multiple extends, you need to
        # destroy the actual node and create many nodes that have
        # mono extend. The first one gets all the css rules
        for _selectors, rules in self.parts.items():
            if ' extends ' in _selectors:
                selectors, _, parent = _selectors.partition(' extends ')
                parents = parent.split('&')
                del self.parts[_selectors]
                for parent in parents:
                    new_selectors = selectors + ' extends ' + parent
                    self.parts.setdefault(new_selectors, [])
                    self.parts[new_selectors].extend(rules)
                    rules = []  # further rules extending other parents will be empty

        cnt = 0
        parents_left = True
        while parents_left and cnt < 10:
            cnt += 1
            parents_left = False
            for _selectors in self.parts.keys():
                selectors, _, parent = _selectors.partition(' extends ')
                if parent:
                    parents_left = True
                    if _selectors not in self.parts:
                        continue  # Nodes might have been renamed while linking parents...

                    rules = self.parts[_selectors]

                    del self.parts[_selectors]
                    self.parts.setdefault(selectors, [])
                    self.parts[selectors].extend(rules)

                    parents = self.link_with_parents(parent, selectors, rules)

                    if parents is None:
                        log.warn("Parent rule not found: %s", parent)
                    else:
                        # from the parent, inherit the context and the options:
                        new_context = {}
                        new_options = {}
                        for parent in parents:
                            new_context.update(parent[CONTEXT])
                            new_options.update(parent[OPTIONS])
                        for rule in rules:
                            _new_context = new_context.copy()
                            _new_context.update(rule[CONTEXT])
                            rule[CONTEXT] = _new_context
                            _new_options = new_options.copy()
                            _new_options.update(rule[OPTIONS])
                            rule[OPTIONS] = _new_options

    @print_timing(3)
    def manage_order(self):
        # order rules according with their dependencies
        for rule in self.rules:
            if rule[POSITION] is not None:
                rule[DEPS].add(rule[POSITION] + 1)
                # This moves the rules just above the topmost dependency during the sorted() below:
                rule[POSITION] = min(rule[DEPS])
        self.rules = sorted(self.rules, key=lambda o: o[POSITION])

    @print_timing(3)
    def parse_properties(self):
        self.css_files = []
        self._rules = {}
        css_files = set()
        old_fileid = None
        for rule in self.rules:
            #print >>sys.stderr, rule[FILEID], rule[POSITION], [ c for c in rule[CONTEXT] if c[1] != '_' ], rule[OPTIONS].keys(), rule[SELECTORS], rule[DEPS]
            if rule[POSITION] is not None and rule[PROPERTIES]:
                fileid = rule[FILEID]
                self._rules.setdefault(fileid, [])
                self._rules[fileid].append(rule)
                if old_fileid != fileid:
                    old_fileid = fileid
                    if fileid not in css_files:
                        css_files.add(fileid)
                        self.css_files.append(fileid)

    @print_timing(3)
    def create_css(self, fileid=None):
        """
        Generate the final CSS string
        """
        if fileid:
            rules = self._rules.get(fileid) or []
        else:
            rules = self.rules

        compress = self.scss_opts.get('compress', True)
        if compress:
            sc, sp, tb, nl = False, '', '', ''
        else:
            sc, sp, tb, nl = True, ' ', '  ', '\n'

        scope = set()
        return self._create_css(rules, scope, sc, sp, tb, nl, not compress and self.scss_opts.get('debug_info', False))

    def _create_css(self, rules, scope=None, sc=True, sp=' ', tb='  ', nl='\n', debug_info=False):
        scope = set() if scope is None else scope

        open_selectors = False
        skip_selectors = False
        old_selectors = None
        open_media = False
        old_media = None
        old_property = None

        wrap = textwrap.TextWrapper(break_long_words=False)
        wrap.wordsep_re = re.compile(r'(?<=,)(\s*)')
        wrap = wrap.wrap

        result = ''
        for rule in rules:
            #print >>sys.stderr, rule[FILEID], rule[MEDIA], rule[POSITION], [ c for c in rule[CONTEXT] if not c.startswith('$__') ], rule[OPTIONS].keys(), rule[SELECTORS], rule[DEPS]
            if rule[POSITION] is not None and rule[PROPERTIES]:
                selectors = rule[SELECTORS]
                media = rule[MEDIA]
                _tb = tb if old_media else ''
                if old_media != media or media is not None:
                    if open_selectors:
                        if not skip_selectors:
                            if not sc:
                                if result[-1] == ';':
                                    result = result[:-1]
                            result += _tb + '}' + nl
                        open_selectors = False
                        skip_selectors = False
                    if open_media:
                        if not sc:
                            if result[-1] == ';':
                                result = result[:-1]
                        result += '}' + nl
                        open_media = False
                    if media:
                        result += '@media ' + (' and ').join(set(media)) + sp + '{' + nl
                        open_media = True
                    old_media = media
                    old_selectors = None  # force entrance to add a new selector
                _tb = tb if media else ''
                if old_selectors != selectors or selectors is not None:
                    if open_selectors:
                        if not skip_selectors:
                            if not sc:
                                if result[-1] == ';':
                                    result = result[:-1]
                            result += _tb + '}' + nl
                        open_selectors = False
                        skip_selectors = False
                    if selectors:
                        if debug_info:
                            filename, lineno = rule[INDEX][rule[LINENO]].rsplit(':', 1)
                            filename = _escape_chars_re.sub(r'\\\1', filename)
                            sass_debug_info = '@media -sass-debug-info{filename{font-family:file\:\/\/%s}line{font-family:\\00003%s}}' % (filename, lineno)
                            result += sass_debug_info + nl
                        _selectors = [s for s in selectors.split(',') if '%' not in s]
                        if _selectors:
                            selector = (',' + sp).join(_selectors) + sp + '{'
                            if nl:
                                selector = nl.join(wrap(selector))
                            result += _tb + selector + nl
                        else:
                            skip_selectors = True
                        open_selectors = True
                    old_selectors = selectors
                    scope = set()
                if selectors:
                    _tb += tb
                if rule[OPTIONS].get('verbosity', 0) > 1:
                    result += _tb + '/* file: ' + rule[FILEID] + ' */' + nl
                    if rule[CONTEXT]:
                        result += _tb + '/* vars:' + nl
                        for k, v in rule[CONTEXT].items():
                            result += _tb + _tb + k + ' = ' + v + ';' + nl
                        result += _tb + '*/' + nl
                if not skip_selectors:
                    result += self._print_properties(rule[PROPERTIES], scope, [old_property], sc, sp, _tb, nl, wrap)

        if open_media:
            _tb = tb
        else:
            _tb = ''
        if open_selectors and not skip_selectors:
            if not sc:
                if result[-1] == ';':
                    result = result[:-1]
            result += _tb + '}' + nl

        if open_media:
            if not sc:
                if result[-1] == ';':
                    result = result[:-1]
            result += '}' + nl

        return result + '\n'

    def _print_properties(self, properties, scope=None, old_property=None, sc=True, sp=' ', _tb='', nl='\n', wrap=None):
        if wrap is None:
            wrap = textwrap.TextWrapper(break_long_words=False)
            wrap.wordsep_re = re.compile(r'(?<=,)(\s*)')
            wrap = wrap.wrap
        result = ''
        old_property = [None] if old_property is None else old_property
        scope = set() if scope is None else scope
        for lineno, prop, value in properties:
            if value is not None:
                if nl:
                    value = (nl + _tb + _tb).join(wrap(value))
                property = prop + ':' + sp + value
            else:
                property = prop
            if '!default' in property:
                property = property.replace('!default', '').replace('  ', ' ').strip()
                if prop in scope:
                    continue
            if old_property[0] != property:
                old_property[0] = property
                scope.add(prop)
                old_property[0] = property
                result += _tb + property + ';' + nl
        return result

    def calculate(self, _base_str, context, options, rule):
        try:
            better_expr_str = self._replaces[_base_str]
        except KeyError:
            better_expr_str = _base_str

            if _skip_word_re.match(better_expr_str) and '- ' not in better_expr_str and ' and ' not in better_expr_str and ' or ' not in better_expr_str and 'not ' not in better_expr_str:
                    self._replaces[_base_str] = better_expr_str
                    return better_expr_str

            better_expr_str = self.do_glob_math(better_expr_str, context, options, rule)

            better_expr_str = eval_expr(better_expr_str, rule, True)
            if better_expr_str is None:
                better_expr_str = self.apply_vars(_base_str, context, options, rule)

            if '$' not in _base_str:
                self._replaces[_base_str] = better_expr_str
        return better_expr_str

    def _calculate_expr(self, context, options, rule, _dequote):
        def __calculate_expr(result):
            _group0 = result.group(1)
            _base_str = _group0
            try:
                better_expr_str = self._replaces[_group0]
            except KeyError:
                better_expr_str = _base_str

                if _skip_re.match(better_expr_str) and '- ' not in better_expr_str:
                    self._replaces[_group0] = better_expr_str
                    return better_expr_str

                better_expr_str = eval_expr(better_expr_str, rule)

                if better_expr_str is None:
                    better_expr_str = _base_str
                elif _dequote:
                    better_expr_str = dequote(better_expr_str)

                if '$' not in _group0:
                    self._replaces[_group0] = better_expr_str

            return better_expr_str
        return __calculate_expr

    def do_glob_math(self, cont, context, options, rule, _dequote=False):
        cont = str(cont)
        if '#{' not in cont:
            return cont
        cont = _expr_glob_re.sub(self._calculate_expr(context, options, rule, _dequote), cont)
        return cont

    @print_timing(3)
    def post_process(self, cont):
        compress = self.scss_opts.get('compress', 1) and 'compress_' or ''
        # short colors:
        if self.scss_opts.get(compress + 'short_colors', 1):
            cont = _short_color_re.sub(r'#\1\2\3', cont)
        # color names:
        if self.scss_opts.get(compress + 'reverse_colors', 1):
            cont = _reverse_colors_re.sub(lambda m: _reverse_colors[m.group(0).lower()], cont)
        if compress:
            # zero units out (i.e. 0px or 0em -> 0):
            cont = _zero_units_re.sub('0', cont)
            # remove zeros before decimal point (i.e. 0.3 -> .3)
            cont = _zero_re.sub('.', cont)
        return cont
