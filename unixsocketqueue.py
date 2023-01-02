# unixsocketqueue.py
# read lines from a unix socket into a queue

# author: krunch3r (KJM github.com/krunch3r76)
# license: General Poetic License (GPL3)

"""
    functor 
        creates a unix socket for listening
        manages a multiprocess that continuously reads from the unix socket
            reads chunk
            parses lines
                adds parsed lines into a multiprocess.queue
                preserves incomplete line in buffer
"""

#############################################
#               imports                     #
#############################################
import multiprocessing
import os, io
from pathlib import Path
import socket
import queue  # queue.empty

# /imports #

#############################################
#               locals                      #
#############################################
# local logging
import logging

logger = logging.getLogger(__name__)
if os.environ.get("KRUNCH3R") is not None:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.CRITICAL)


handler = logging.StreamHandler()
formatter = logging.Formatter(
    style="{", fmt="[{filename}:{funcName}:{lineno}] {message}"
)
handler.setFormatter(formatter)

logger.addHandler(handler)
# / end local logging

# private functions
def _strip_ansi(text):
    # strip ansi codes from text and return
    # credit. chat.openai.com
    import re

    stripped_text = re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", text)
    return stripped_text


# /private functions


# private classes
class _SocketListener:
    # functor that reads socket data into a buffer and parses lines into a (shared) queue

    def __init__(self, shared_queue: multiprocessing.Queue, socket, strip_ansi):
        """
        Args:
            shared_queue: shared queue
            socket: socket object (not listening, not connected)
            strip_ansi: flag to strip ansi escape codes before adding lines to queue

        Raises:
            BrokenPipeError: when connection is closed on other end
        """
        self.shared_queue = shared_queue
        self.socket = socket
        self.buffer = io.StringIO()
        self.strip_ansi = strip_ansi

    def _parse_buffer(self):
        # split lines but preserve incomplete line
        self.buffer.seek(0)
        current_line = self.buffer.readline()
        while current_line.endswith("\n"):
            if not self.strip_ansi:
                self.shared_queue.put_nowait(current_line[:-1])
            else:
                self.shared_queue.put_nowait(_strip_ansi(current_line[:-1]))
            current_line = self.buffer.readline()
        self.buffer.close()  # delete buffer
        self.buffer = io.StringIO()
        self.buffer.write(current_line)  # put partial line into new buffer

    def __call__(self):
        # wait for connection then read next available into parser
        self.socket.listen(1)
        conn, accept = self.socket.accept()
        while True:
            data_received = conn.recv(4096)
            if len(data_received) == 0:
                raise BrokenPipeError
            text_received = data_received.decode("utf-8")
            self.buffer.write(text_received)
            self._parse_buffer()


# /private classes

# / locals #


#########################################
#           exports                     #
#########################################
class UnixSocketQueue:
    """
    create a socket that accepts a connection then reads lines into a shared queue

    Raises:
        FileExistsError for when the socket address already exists

    Notes:
        implements get_nowait() functionality of a python Queue
    """

    def __init__(self, socket_filepath, strip_ansi=False):
        """
        Args:
            socket_filepath: stringable object where the socket shall be created
            strip_ansi: flag to strip ansi before adding a line to the queue

        """
        self.strip_ansi = strip_ansi
        self.socket_filepath_obj = Path(socket_filepath).resolve()  # normalize

        if self.socket_filepath_obj.exists():
            raise FileExistsError(
                f"CANNOT CREATE LISTENER AT {self.socket_filepath_obj}, file exists!"
            )

        self.socket_obj = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket_obj.bind(str(self.socket_filepath_obj))

        if self.socket_filepath_obj.is_socket():
            logger.log(logging.DEBUG, f"socket created: {self.socket_filepath_obj}")

        self.data = multiprocessing.Queue()

        socketListener = _SocketListener(self.data, self.socket_obj, strip_ansi)
        self.process = multiprocessing.Process(target=socketListener, daemon=True)
        self.process.start()

    def get_nowait(self):
        # call wrapped queue's get_nowait method and return result or re-raise exception
        try:
            line = self.data.get_nowait()
        except queue.Empty:
            if self.process.exitcode is not None:
                try:
                    self.process.join()  # capture any exceptions
                except BrokenPipeError:
                    raise  # BrokenPipeError
                else:
                    raise  # queue.Empty or something unforeseen
            else:
                raise  # queue.Empty implying connection still good just empty queue
        else:
            return line

    def __del__(self):
        # close and unlink the socket created upon initialization
        if self.socket_filepath_obj.is_socket():
            self.socket_obj.close()
        self.socket_filepath_obj.unlink(True)


#####################################
#           example logic           #
#####################################
if __name__ == "__main__":
    """
    after running this main logic, create a unix socket that receives the stdout of
    a program by combining linux executables tee and ncat ("nc") like so:
    $ golemsp run --payment-network testnet 2>&1 | tee  >(nc -U /tmp/golemsp.sock)
    """
    unixSocketQueue = UnixSocketQueue("/tmp/golemsp.sock")

    while True:
        import time

        try:
            line = unixSocketQueue.data.get_nowait()
        except queue.Empty:
            pass
        else:
            print(line)
            input()
