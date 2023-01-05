# ProcessQueue
A queue that fills with the line by line output of a subprocess.
Upon instantation it runs the command line specified and starts filling
the queue.

Tested on linux and windows 11 with Python 3.9 and above. Minimum Python
version expected to be 3.7.

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
the output of a subprocess will always present a risk of a deadlock. The
Python docs give this warning:
```
Warning

Use communicate() rather than .stdin.write, .stdout.read or .stderr.read to
avoid deadlocks due to any of the other OS pipe buffers filling up and blocking
the child process. 
```
[1]

This implementation works around the standard implementation by reading
from the file descriptors as soon as data is written to them instead
of relying on the popen/StreamReader paradigm.

## ProcessQueue example usage
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
            print(next_line)
```

# UnixSocketQueue
A queue that creates a unix socket and listens for a (single) connection
or connects to an existing unix socket (multiply) that is already listening;
fills the queue with the line by line output.

This is useful when a separation of privileges is required on a local system, where another user is granted access to the unix pipe. It can also be useful to set up a program as a server and run it (and other copies) as clients to handle the simultaneous output differently according to each client's logic. However, UDPSocketQueue would be more practical and flexible when access control to information is not a concern. UnixSocketQueue is here as an alternative.

## as server
```bash
$ python3 main.py # instantiates with whether_server=True #default
$ golemsp run --payment-network testnet 2>&1 | tee  >(nc -U /tmp/golemsp.sock)
```

## as client
```bash
$ golemsp run --payment-network testnet 2>&1 | tee  >(nc --keep-open -lU /tmp/golemsp.sock)
$ python3 main.py # instantiates queue with whether_server=False
```
# FileQueue
A queue that reads and tails a file pushing complete lines. Useful for parsing output piped to a file as by tee -a.

# StdinQueue
TBA: A queue that reads text piped to stdin. Useful to parsing a console program's output realtime.

# UDPSocketQueue
TBA: A queue that pushes unto itself lines from a udp socket as they become available.

References:
[1] https://docs.python.org/3/library/subprocess.html#subprocess.Popen.stderr
