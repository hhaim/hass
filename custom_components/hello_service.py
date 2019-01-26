import logging

# The domain of your component. Should be equal to the name of your component.
DOMAIN = 'hello_service'

ATTR_NAME = 'name'
DEFAULT_NAME = 'World'

_LOGGER = logging.getLogger(__name__)


from collections import defaultdict
import gc, sys

#### mem_top

def mem_top(limit=10, width=100, sep='\n', refs_format='{num}\t{type} {obj}', bytes_format='{num}\t {obj}', types_format='{num}\t {obj}', verbose_types=None, verbose_file_name='/tmp/mem_top'):

    gc.collect()
    objs = gc.get_objects()

    nums_by_types = defaultdict(int)
    reprs_by_types = defaultdict(list)

    for obj in objs:
        _type = type(obj)
        nums_by_types[_type] += 1
        if verbose_types and _type in verbose_types:
            reprs_by_types[_type].append(_repr(obj))

    if verbose_types:
        verbose_result = sep.join(sep.join(
            types_format.format(num=len(s), obj=s[:width])
            for s in sorted(reprs_by_types[_type], key=lambda s: -len(s))
        ) for _type in verbose_types)

        if verbose_file_name:
            with open(verbose_file_name, 'w') as f:
                f.write(verbose_result)
        else:
            return verbose_result

    return sep.join((
        '',
        'refs:',
        _top(limit, width, sep, refs_format, (
            (len(gc.get_referents(obj)), obj) for obj in objs
        )),
        '',
        'bytes:',
        _top(limit, width, sep, bytes_format, (
            (sys.getsizeof(obj), obj) for obj in objs
        )),
        '',
        'types:',
        _top(limit, width, sep, types_format, (
            (num, _type) for _type, num in nums_by_types.items()
        )),
        '',
    ))

#### _top

def _top(limit, width, sep, format, nums_and_objs):
    return sep.join(
        format.format(num=num, type=type(obj), obj=_repr(obj)[:width])
        for num, obj in sorted(nums_and_objs, key=lambda num_obj: -num_obj[0])[:limit]
    )

#### _repr

def _repr(obj):
    try:
        return repr(obj)
    except Exception:
        return '(broken __repr__, type={})'.format(type(obj))



def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""

    def handle_hello(call):
        with open("/tmp/mem.txt", "a") as myfile:
            myfile.write(mem_top())

    hass.services.register(DOMAIN, 'hello', handle_hello)

    # Return boolean to indicate that initialization was successfully.
    return True





