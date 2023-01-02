# read lines from a unix socket into a queue
import multiprocessing
import os, io
from pathlib import Path
import socket

"""
    functor 
        creates a unix socket for listening
        manages a multiprocess that continuously reads from the unix socker
            buffers data
            parses lines
                adds parsed lines into a multiprocess.queue

    requirements:
        overwrite dangling listeners
            challenge: ensure listener is in fact dangling
        consider making the unixsocket file non-blocking (if needed tho multiprocessing)
    todo:
        use a specific exception for when the listener file exists
"""


def _strip_ansi(text):
    # strip ansi codes from text and return
    # credit. chat.openai.com
    import re

    stripped_text = re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", text)
    return stripped_text


class _SocketListener:
    # functor that reads socket data into a buffer and parses lines into a (shared) queue

    def __init__(self, shared_queue: multiprocessing.Queue, socket, strip_ansi):
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
        self.buffer.close()
        self.buffer = io.StringIO()
        self.buffer.write(current_line)  # put back partial line

    def __call__(self):
        # wait for connection then read next available into parser
        self.socket.listen(1)
        conn, accept = self.socket.accept()
        while True:
            data_received = conn.recv(4096)
            text_received = data_received.decode("utf-8")
            self.buffer.write(text_received)
            self._parse_buffer()


class UnixSocketQueue:
    def __init__(self, socket_filepath, strip_ansi=False):
        """
        Args:
            socket_filepath: stringable object where the socket shall be created
            strip_ansi: flag to strip ansi before adding a line to the queue

        """
        self.strip_ansi = strip_ansi
        self.socket_filepath_obj = Path(socket_filepath).resolve()  # normalize

        if self.socket_filepath_obj.exists():
            raise Exception(
                f"CANNOT CREATE LISTENER AT {self.socket_filepath_obj}, file exists!"
            )

        self.socket_obj = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket_obj.bind(str(self.socket_filepath_obj))

        if self.socket_filepath_obj.is_socket():
            print(f"socket created: {self.socket_filepath_obj}")

        self.data = multiprocessing.Queue()

        socketListener = _SocketListener(self.data, self.socket_obj, strip_ansi)
        process = multiprocessing.Process(target=socketListener, daemon=True)
        process.start()

    def get_nowait(self):
        try:
            line = self.data.get_nowait()
        except Exception as e:
            raise
        else:
            return line

    def __del__(self):
        # close and unlink the socket created upon initialization
        self.socket_obj.close()
        self.socket_filepath_obj.unlink(True)


if __name__ == "__main__":
    unixSocketQueue = UnixSocketQueue("/tmp/blah13")

    while True:
        import time

        try:
            line = unixSocketQueue.data.get_nowait()
        except:
            pass
        else:
            print(line)
            input()
