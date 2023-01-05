import os

from .processqueue import ProcessQueue
from .filequeue import FileQueue

if os.name == "posix":
    from .unixsocketqueue import UnixSocketQueue
