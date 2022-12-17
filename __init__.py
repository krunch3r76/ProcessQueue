#!/bin/python3
"""Run an executable and queue its output line by line (non-blocking)

author: krunch3r (KJM github.com/krunch3r76)
license: General Poetic License (GPL3)

ProcessQueue utilizes a multiprocess.Queue as a shared data structure that
is written to from a subprocess instantiated in the multiprocess thread.
The module implements a custom ProtocolFactory (via the asyncio subprocess
routines) to intercept data output by the subprocess into a line buffer
which is emptied unto the shared queue whenever a newline is encountered.

ProcessQueue is instantiated with the command line that will execute
in the multiprocess-subprocess enclave immediately and indepedently
of any additional interaction. The queue can be de-queued or popped
to retrieve the lines currently queued at any given time via the
ProcessQueue.get_nowait() method. Consumers must handle two kinds of
exceptions: the standard queue.Empty exception indicating that presently
there is nothing to read from the queue and the processqueue.ProcessTerminated
exception indicating that not only is the queue empty but the process has
been terminated.
"""


import asyncio
import subprocess
import io
import queue  # except queue.Empty
import multiprocessing


class ProcessTerminated(Exception):
    """indicate that an empty queue is no longer readable as it will never be filled further"""

    def __init__(self, message="Empty queue and process has terminated"):
        self.message = message


class _MySubprocessProtocol(asyncio.SubprocessProtocol):
    """subclass the protocal factory SubprocessProtocol to handle output of associated transport

    parses data into lines whilst buffering incomplete lines

    Currently the file descriptor is treated indiscimrinately so that stderr and stdout
    are considered part of the same output. Assumes no interleaving before complete
    outputs! REVIEW pipe_data_received
    """

    def __init__(self, *args, shared_queue, **kwargs):
        """initializes to reference the shared queue and a fresh linebuffer memory stream

        Args:
            shared_queue: the interprocess python queue
        """
        self._queue = shared_queue
        self._linebuffer = io.StringIO()
        super().__init__(*args, **kwargs)

    def pipe_data_received(self, fd, data):
        """buffer incomplete and queue lines from process's output(s)

        reads each byte from the data into a memory buffer and flushing complete lines
        into the class's shared queue

        Args:
            fd: the file descriptor providing the data from the transport (e.g. 1, 2)
            data: data written to the file descripto

        Returns:
            None

        Raises:
            None
        """
        for byte in data:
            char = chr(byte)
            if char != "\n":
                self._linebuffer.write(char)
            else:
                self._queue.put_nowait(self._linebuffer.getvalue())
                self._linebuffer.close()
                self._linebuffer = io.StringIO()

        super().pipe_data_received(fd, data)  # follow internal paths


async def _tail_subprocess(shared_queue, cmdline):
    """launches a command line in a subprocess

    Launches then loops until the subprocess has terminated.

    Args:
        shared_queue: the shared queue with the main thread
        cmdline: the list of strings representing the full command to be run

    Returns:
        None

    Raises:
        None
    """
    # save, interesting alternative to using the callback is to make a runtime class
    # MySubprocessProtocolTyped = type(
    #     "MySubprocessProtocolTyped", (MySubprocessProtocol_,), {"child_pipe": child_pipe}
    # )
    loop = asyncio.get_event_loop()

    transport, _ = await loop.subprocess_exec(
        lambda: _MySubprocessProtocol(shared_queue=shared_queue),
        *cmdline,
    )

    subproc = transport.get_extra_info("subprocess")  # popen instance

    # loop
    while subproc.poll() is None:
        await asyncio.sleep(1)

    # process has ended


class ProcessQueue:
    """execute a subprocess and queue its output line by line non-blocking

    Implements get_nowait() to read any lines output by the command launched upon
    initialization.

    get_nowait() throws two kinds of exceptions that must be handled:
        queue.Empty indicating there was no line in the queue
        processqueue.ProcessTerminating indicating there is no line and
            that there cannot be any more lines to be read as the process
            has terminated.
    """

    def __init__(
        self,
        cmdline,
    ):
        """inits ProcessQueue with a shared queue and invoked the function to launch the command

        the initialized shared queue is immediately passed into a multiprocessing thread along
        with the command to be run. it is then daemonized.

        Args:
            cmdline: a sequence (e.g. list) of text commands representing the full command line
                to execute
        """

        # def __run_tail_subprocess_asynchronously(sharedQueue, cmdline):
        #     asyncio.run(_tail_subprocess(sharedQueue, cmdline))

        self._queue = multiprocessing.Queue()

        self._process = multiprocessing.Process(
            target=asyncio.run,
            args=(_tail_subprocess(self._queue, cmdline),),
            daemon=True,
        )
        # self._process = multiprocessing.Process(
        #     target=__run_tail_subprocess_asynchronously,
        #     args=(
        #         self._queue,
        #         cmdline,
        #     ),
        # )
        self._process.start()

    def get_nowait(self):
        """returns a line from a queue or throws one of two exceptions

        invokes multiprocessing.Queue.get_nowait() to get an available line element
        from the queue but abstracts a thrown queue.Empty exception to throw a
        ProcessTerminated exception if appropriate in lieu.

        Returns:
            a line of text terminated by a newline

        Raises:
            queue.Empty: there is currently no line to read from the queue
            ProcessTerminated: there cannot be any more lines to read from the queue:
                the process has terminated.
        """
        try:
            line = self._queue.get_nowait()
        except queue.Empty as exc:
            if self._process.exitcode is not None:
                raise ProcessTerminated from exc
            raise
        else:
            return line


# example usage
if __name__ == "__main__":
    processQueue = ProcessQueue(
        cmdline=["/home/golem/.local/bin/golemsp", "run", "--payment-network=testnet"]
    )
    while True:
        try:
            import time

            time.sleep(0.01)
            next_line = processQueue.get_nowait()
        except queue.Empty:
            pass
        except ProcessTerminated:
            print("process terminated! and queue is empty")
            break
        else:
            print(next_line)
