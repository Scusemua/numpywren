from redis_alt.client import RedisAlt, StrictRedisAlt
from redis_alt.connection import (
    BlockingConnectionPool,
    ConnectionPool,
    Connection,
    SSLConnection,
    UnixDomainSocketConnection
)
from redis_alt.utils import from_url
from redis_alt.exceptions import (
    AuthenticationError,
    AuthenticationWrongNumberOfArgsError,
    BusyLoadingError,
    ChildDeadlockedError,
    ConnectionError,
    DataError,
    InvalidResponse,
    PubSubError,
    ReadOnlyError,
    RedisAltError,
    ResponseError,
    TimeoutError,
    WatchError
)


def int_or_str(value):
    try:
        return int(value)
    except ValueError:
        return value


__version__ = '3.4.1'
VERSION = tuple(map(int_or_str, __version__.split('.')))

__all__ = [
    'AuthenticationError',
    'AuthenticationWrongNumberOfArgsError',
    'BlockingConnectionPool',
    'BusyLoadingError',
    'ChildDeadlockedError',
    'Connection',
    'ConnectionError',
    'ConnectionPool',
    'DataError',
    'from_url',
    'InvalidResponse',
    'PubSubError',
    'ReadOnlyError',
    'RedisAlt',
    'RedisAltError',
    'ResponseError',
    'SSLConnection',
    'StrictRedisAlt',
    'TimeoutError',
    'UnixDomainSocketConnection',
    'WatchError',
]
