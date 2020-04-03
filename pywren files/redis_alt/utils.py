from contextlib import contextmanager


try:
    import hiredis
    HIREDIS_AVAILABLE = True
except ImportError:
    HIREDIS_AVAILABLE = False


def from_url(url, db=None, **kwargs):
    """
    Returns an active RedisAlt client generated from the given database URL.

    Will attempt to extract the database id from the path url fragment, if
    none is provided.
    """
    from redis_alt.client import RedisAlt
    return RedisAlt.from_url(url, db, **kwargs)


@contextmanager
def pipeline(redis_alt_obj):
    p = redis_alt_obj.pipeline()
    yield p
    p.execute()


class dummy(object):
    """
    Instances of this class can be used as an attribute container.
    """
    pass
