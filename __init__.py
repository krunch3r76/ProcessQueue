import os

from .processqueue import ProcessQueue

if os.name == "posix":
    from .unixsocketqueue import UnixSocketQueue
