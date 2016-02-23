import sys
import time
import os
import errno
import shlex
import pydoc
import inspect
import re

color2num = dict(
    gray=30,
    red=31,
    green=32,
    yellow=33,
    blue=34,
    magenta=35,
    cyan=36,
    white=37,
    crimson=38
)


def colorize(string, color, bold=False, highlight=False):
    attr = []
    num = color2num[color]
    if highlight:
        num += 10
    attr.append(str(num))
    if bold:
        attr.append('1')
    return '\x1b[%sm%s\x1b[0m' % (';'.join(attr), string)


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def log(s):  # , send_telegram=False):
    print s
    sys.stdout.flush()


class SimpleMessage(object):

    def __init__(self, msg, logger=log):
        self.msg = msg
        self.logger = logger

    def __enter__(self):
        print self.msg
        self.tstart = time.time()

    def __exit__(self, etype, *args):
        maybe_exc = "" if etype is None else " (with exception)"
        self.logger("done%s in %.3f seconds" %
                    (maybe_exc, time.time() - self.tstart))


MESSAGE_DEPTH = 0


class Message(object):

    def __init__(self, msg):
        self.msg = msg

    def __enter__(self):
        global MESSAGE_DEPTH  # pylint: disable=W0603
        print colorize('\t' * MESSAGE_DEPTH + '=: ' + self.msg, 'magenta')
        self.tstart = time.time()
        MESSAGE_DEPTH += 1

    def __exit__(self, etype, *args):
        global MESSAGE_DEPTH  # pylint: disable=W0603
        MESSAGE_DEPTH -= 1
        maybe_exc = "" if etype is None else " (with exception)"
        print colorize('\t' * MESSAGE_DEPTH + "done%s in %.3f seconds" % (maybe_exc, time.time() - self.tstart), 'magenta')


def prefix_log(prefix, logger=log):
    return lambda s: logger(prefix + s)


def tee_log(file_name):
    f = open(file_name, 'w+')

    def logger(s):
        log(s)
        f.write(s)
        f.write('\n')
        f.flush()
    return logger


def collect_args():
    splitted = shlex.split(' '.join(sys.argv[1:]))
    return {arg_name[2:]: arg_val
            for arg_name, arg_val in zip(splitted[::2], splitted[1::2])}


def type_hint(arg_name, arg_type):
    def wrap(f):
        meta = getattr(f, '__tweak_type_hint_meta__', None)
        if meta is None:
            f.__tweak_type_hint_meta__ = meta = {}
        meta[arg_name] = arg_type
        return f
    return wrap


def tweak(fun_or_val, identifier=None):
    if callable(fun_or_val):
        return tweakfun(fun_or_val, identifier)
    return tweakval(fun_or_val, identifier)


def tweakval(val, identifier):
    if not identifier:
        raise ValueError('Must provide an identifier for tweakval to work')
    args = collect_args()
    for k, v in args.iteritems():
        stripped = k.replace('-', '_')
        if stripped == identifier:
            log('replacing %s in %s with %s' % (stripped, str(val), str(v)))
            return type(val)(v)
    return val


def tweakfun(fun, alt=None):
    """Make the arguments (or the function itself) tweakable from command line.
    See tests/test_misc_console.py for examples.

    NOTE: this only works for the initial launched process, since other processes
    will get different argv. What this means is that tweak() calls wrapped in a function
    to be invoked in a child process might not behave properly.
    """
    cls = getattr(fun, 'im_class', None)
    method_name = fun.__name__
    if alt:
        cmd_prefix = alt
    elif cls:
        cmd_prefix = cls + '.' + method_name
    else:
        cmd_prefix = method_name
    cmd_prefix = cmd_prefix.lower()
    args = collect_args()
    if cmd_prefix in args:
        fun = pydoc.locate(args[cmd_prefix])
    if type(fun) == type:
        argspec = inspect.getargspec(fun.__init__)
    else:
        argspec = inspect.getargspec(fun)
    # TODO handle list arguments
    defaults = dict(
        zip(argspec.args[-len(argspec.defaults or []):], argspec.defaults or []))
    replaced_kwargs = {}
    cmd_prefix += '-'
    if type(fun) == type:
        meta = getattr(fun.__init__, '__tweak_type_hint_meta__', {})
    else:
        meta = getattr(fun, '__tweak_type_hint_meta__', {})
    for k, v in args.iteritems():
        if k.startswith(cmd_prefix):
            stripped = k[len(cmd_prefix):].replace('-', '_')
            if stripped in meta:
                log('replacing %s in %s with %s' % (stripped, str(fun), str(v)))
                replaced_kwargs[stripped] = meta[stripped](v)
            elif stripped not in argspec.args:
                raise ValueError(
                    '%s is not an explicit parameter of %s' % (stripped, str(fun)))
            elif stripped not in defaults:
                raise ValueError(
                    '%s does not have a default value in method %s' % (stripped, str(fun)))
            elif defaults[stripped] is None:
                raise ValueError(
                    'Cannot infer type of %s in method %s from None value' % (stripped, str(fun)))
            else:
                log('replacing %s in %s with %s' % (stripped, str(fun), str(v)))
                # TODO more proper conversions
                replaced_kwargs[stripped] = type(defaults[stripped])(v)

    def tweaked(*args, **kwargs):
        all_kw = dict(zip(argspec[0], args) +
                      kwargs.items() + replaced_kwargs.items())
        return fun(**all_kw)
    return tweaked


_find_unsafe = re.compile(r'[a-zA-Z0-9_^@%+=:,./-]').search


def _shellquote(s):
    """Return a shell-escaped version of the string *s*."""
    if not s:
        return "''"

    if _find_unsafe(s) is None:
        return s

    # use single quotes, and put single quotes into double quotes
    # the string $'b is then quoted as '$'"'"'b'

    return "'" + s.replace("'", "'\"'\"'") + "'"


def _to_param_val(v):
    if v is None:
        return ""
    elif isinstance(v, list):
        return " ".join(map(_shellquote, map(str, v)))
    else:
        return _shellquote(str(v))


def to_command(params):
    command = "python scripts/run_experiment.py"
    for k, v in params.iteritems():
        if isinstance(v, dict):
            for nk, nv in v.iteritems():
                if str(nk) == "_name":
                    command += "  --%s %s" % (k, _to_param_val(nv))
                else:
                    command += \
                        "  --%s_%s %s" % (k, nk, _to_param_val(nv))
        else:
            command += "  --%s %s" % (k, _to_param_val(v))
    return command


def run_experiment(params):
    command = to_command(params)
    os.system(command)
