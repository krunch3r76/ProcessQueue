# ProcessQueue
A queue that fills with the line by line output of a subprocess

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

Note: While ProcessQueue utilizes an asynchronous event loop in a separate
multiprocess "thread" it does not require asynchronous calls to it.

tl;dr: python's asyncio subprocess routines are overridden to pass data
to a multiprocess.Queue instead of a streamreader PIPE.

The problem this module solves is that the Python standard way of reading
the output of a subprocess will always present a risk of a deadlock
depending on whether the StreamReader is accessed while the OS is filling
pipes. (Add python docs reference here later). This implementation avoids
the "polling" by automatically filling a queue when the data becomes
available, the "polling" the queue itself does not trigger any OS event.

# example usage
```python
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
            print(next_line, end="")
```
