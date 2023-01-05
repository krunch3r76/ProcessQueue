# filequeue.py
"""tail a file to read line by line into a queue

exports FileQueue that wraps a python Queue object exposing get_nowait()
the queue is filled by all lines the file which is monitored for additional data

author: krunch3r (KJM github.com/krunch3r76)
license: General Poetic License (GPL3)

"""

from pathlib import Path
import multiprocessing
import io


class ReadLineBuffer:
    # read all available lines (incomplete or complete) from file-like object and callback
    # wraps a StringIO

    def __init__(self, targetBinaryFile, on_complete_line):
        """
        Args:
            targetBinaryFile: an open file object stream that can be read (binary)
            on_complete_line: a callback taking a line without a line ending as an argument
        """
        self._data = io.StringIO()
        self._targetBinaryFile = targetBinaryFile
        self._on_complete_line = on_complete_line

    def __call__(self):
        """read all data from file object stream and retain an incomplete line in buffer

        invokes the callback set on initialization for each complete line
        """
        # read lines
        self._data.write(self._targetBinaryFile.read().decode("utf-8"))
        self._data.seek(0)  # read from start
        value = self._data.getvalue()
        lines = value.splitlines(keepends=True)
        for current_line in lines:
            if current_line.endswith("\n"):
                self._on_complete_line(current_line[:-1])
        self._data.close()
        self._data = io.StringIO()
        self._data.write(current_line)


class FileQueue:
    # open a file and queue lines as they become available (tail)

    def __init__(self, path_to_file):
        """
        Args:
            path_to_file: a path as input to a python pathlib.Path object
        """
        self._pathFile = Path(path_to_file)
        self._queueShared = multiprocessing.Queue()
        self._fileOpen = self._pathFile.open(mode="rb")
        self._readLineBuffer = ReadLineBuffer(
            self._fileOpen, lambda line: self._queueShared.put_nowait(line)
        )
        self._multiprocess = multiprocessing.Process(
            target=self._readLineBuffer, daemon=True
        )
        self._multiprocess.start()

    def get_nowait(self):
        """call get_nowait on wrapped Queue
        Raises:
            queue.Empty on an empty queue
        """
        return self._queueShared.get_nowait()


if __name__ == "__main__":
    import sys
    import time
    import queue

    fileQueue = FileQueue(sys.argv[1])

    while True:
        try:
            line = fileQueue.get_nowait()
        except queue.Empty:
            time.sleep(0.001)
        else:
            print(line)
