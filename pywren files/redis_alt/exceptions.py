"Core exceptions raised by the RedisAlt client"


class RedisAltError(Exception):
    pass


class ConnectionError(RedisAltError):
    pass


class TimeoutError(RedisAltError):
    pass


class AuthenticationError(ConnectionError):
    pass


class BusyLoadingError(ConnectionError):
    pass


class InvalidResponse(RedisAltError):
    pass


class ResponseError(RedisAltError):
    pass


class DataError(RedisAltError):
    pass


class PubSubError(RedisAltError):
    pass


class WatchError(RedisAltError):
    pass


class NoScriptError(ResponseError):
    pass


class ExecAbortError(ResponseError):
    pass


class ReadOnlyError(ResponseError):
    pass


class NoPermissionError(ResponseError):
    pass


class LockError(RedisAltError, ValueError):
    "Errors acquiring or releasing a lock"
    # NOTE: For backwards compatability, this class derives from ValueError.
    # This was originally chosen to behave like threading.Lock.
    pass


class LockNotOwnedError(LockError):
    "Error trying to extend or release a lock that is (no longer) owned"
    pass


class ChildDeadlockedError(Exception):
    "Error indicating that a child process is deadlocked after a fork()"
    pass


class AuthenticationWrongNumberOfArgsError(ResponseError):
    """
    An error to indicate that the wrong number of args
    were sent to the AUTH command
    """
    pass
