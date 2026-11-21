import sys
import time
import errno
import socket
import threading
from boltons.socketutils import (BufferedSocket,
                                 NetstringSocket,
                                 ConnectionClosed,
                                 Error,
                                 NetstringInvalidSize,
                                 NetstringMessageTooLong,
                                 NetstringProtocolError,
                                 MessageTooLong,
                                 Timeout)

import pytest

# skip if there's no socketpair
pytestmark = pytest.mark.skipif(getattr(socket, 'socketpair', None) is None,
                                reason='no socketpair (likely Py2 on Windows)')


def test_short_lines():
    for ms in (2, 4, 6, 1024, None):
        x, y = socket.socketpair()
        bs = BufferedSocket(x)
        y.sendall(b'1\n2\n3\n')
        assert bs.recv_until(b'\n', maxsize=ms) == b'1'
        assert bs.recv_until(b'\n', maxsize=ms) == b'2'
        y.close()
        assert bs.recv_close(maxsize=ms) == b'3\n'

        try:
            bs.recv_size(1)
        except ConnectionClosed:
            pass
        else:
            assert False, 'expected ConnectionClosed'

        bs.close()
    return


def test_multibyte_delim():
    """Primarily tests recv_until with various maxsizes and True/False
    for with_delimiter.
    """

    delim = b'\r\n'
    for with_delim in (True, False):
        if with_delim:
            cond_delim = b'\r\n'
        else:
            cond_delim = b''

        empty = b''
        small_one = b'1'
        big_two = b'2' * 2048
        for ms in (3, 5, 1024, None):
            x, y = socket.socketpair()
            bs = BufferedSocket(x)

            y.sendall(empty + delim)
            y.sendall(small_one + delim)
            y.sendall(big_two + delim)

            kwargs = {'maxsize': ms, 'with_delimiter': with_delim}
            assert bs.recv_until(delim, **kwargs) == empty + cond_delim
            assert bs.recv_until(delim, **kwargs) == small_one + cond_delim
            try:
                assert bs.recv_until(delim, **kwargs) == big_two + cond_delim
            except MessageTooLong:
                if ms is None:
                    assert False, 'unexpected MessageTooLong'
            else:
                if ms is not None:
                    assert False, 'expected MessageTooLong'

    return


def test_props():
    x, y = socket.socketpair()
    bs = BufferedSocket(x)

    assert bs.type == x.type
    assert bs.proto == x.proto
    assert bs.family == x.family
    return


def test_buffers():
    x, y = socket.socketpair()
    bx, by = BufferedSocket(x), BufferedSocket(y)

    assert by.getrecvbuffer() == b''
    assert by.getsendbuffer() == b''

    assert bx.getrecvbuffer() == b''

    by.buffer(b'12')
    by.sendall(b'3')
    assert bx.recv_size(1) == b'1'

    assert bx.getrecvbuffer() == b'23'

    return


def test_client_disconnecting():
    def get_bs_pair():
        x, y = socket.socketpair()
        bx, by = BufferedSocket(x), BufferedSocket(y)

        # sanity check
        by.sendall(b'123')
        bx.recv_size(3) == b'123'

        return bx, by

    bx, by = get_bs_pair()
    assert bx.fileno() > 0

    bx.close()
    assert bx.getrecvbuffer() == b''

    try:
        bx.recv(1)
    except OSError:
        pass
    else:
        assert False, 'expected socket.error on closed recv'

    assert bx.fileno() == -1

    by.buffer(b'123')
    assert by.getsendbuffer()
    try:
        by.flush()
    except OSError:
        assert by.getsendbuffer() == b'123'
    else:
        if sys.platform != 'win32':  # Windows socketpairs are kind of bad
            assert False, 'expected socket.error broken pipe'

    try:
        by.shutdown(socket.SHUT_RDWR)
    except OSError:
        # Mac sockets are already shut down at this point. See #71.
        if sys.platform != 'darwin':
            raise

    by.close()
    assert not by.getsendbuffer()

    try:
        by.send(b'123')
    except OSError:
        pass
    else:
        assert False, 'expected socket.error on closed send'

    return


def test_split_delim():
    delim = b'\r\n'
    first = b'1234\r'
    second = b'\n5'

    x, y = socket.socketpair()
    bs = BufferedSocket(x)

    y.sendall(first)
    try:
        bs.recv_until(delim, timeout=0.0001)
    except Timeout:
        pass
    y.sendall(second)

    assert bs.recv_until(delim, with_delimiter=True) == b'1234\r\n'
    assert bs.recv_size(1) == b'5'
    return


def test_basic_nonblocking():
    delim = b'\n'

    # test with per-call timeout
    x, y = socket.socketpair()
    bs = BufferedSocket(x)

    try:
        bs.recv_until(delim, timeout=0)
    except OSError as se:
        assert se.errno == errno.EWOULDBLOCK
    y.sendall(delim)  # sending an empty message, effectively
    assert bs.recv_until(delim) == b''

    # test with instance-level default timeout
    x, y = socket.socketpair()
    bs = BufferedSocket(x, timeout=0)

    try:
        bs.recv_until(delim)
    except OSError as se:
        assert se.errno == errno.EWOULDBLOCK
    y.sendall(delim)
    assert bs.recv_until(delim) == b''

    # test with setblocking(0) on the underlying socket
    x, y = socket.socketpair()
    x.setblocking(0)
    bs = BufferedSocket(x)

    try:
        bs.recv_until(delim)
    except OSError as se:
        assert se.errno == errno.EWOULDBLOCK
    y.sendall(delim)
    assert bs.recv_until(delim) == b''

    return


def test_recv_size_zero():
    x, y = socket.socketpair()
    x.setblocking(0)
    bs = BufferedSocket(x)
    assert bs.recv_size(0) == b''

    y.sendall(b'abc')
    assert bs.recv_size(1) == b'a'
    assert bs.recv_size(0) == b''
    assert bs.recv_size(2) == b'bc'


def test_simple_buffered_socket_passthroughs():
    x, y = socket.socketpair()
    bs = BufferedSocket(x)

    assert bs.getsockname() == x.getsockname()
    assert bs.getpeername() == x.getpeername()


def test_timeout_setters_getters():
    x, y = socket.socketpair()
    bs = BufferedSocket(x)

    assert bs.settimeout(1.0) is None
    assert bs.gettimeout() == 1.0

    assert bs.setblocking(False) is None
    assert bs.gettimeout() == 0.0

    assert bs.setblocking(True) is None
    assert bs.gettimeout() is None


def netstring_server(server_socket):
    "A basic netstring server loop, supporting a few operations"
    try:
        while True:
            clientsock, addr = server_socket.accept()
            client = NetstringSocket(clientsock)
            while 1:
                request = client.read_ns()
                if request == b'close':
                    clientsock.close()
                    break
                elif request == b'shutdown':
                    return
                elif request == b'reply4k':
                    client.write_ns(b'a' * 4096)
                elif request == b'ping':
                    client.write_ns(b'pong')
                elif request == b'reply128k':
                    client.setmaxsize(128 * 1024)
                    client.write_ns(b'huge' * 32 * 1024)  # 128kb
                    client.setmaxsize(32768)  # back to default
    except Exception as e:
        print('netstring_server exiting with error: %r' % e)
        raise


def test_socketutils_netstring():
    """A holistic feature test of BufferedSocket via the NetstringSocket
    wrapper. Runs
    """
    print("running self tests")

    # Set up server
    server_socket = socket.socket()
    server_socket.bind(('127.0.0.1', 0))  # localhost with ephemeral port
    server_socket.listen(100)
    ip, port = server_socket.getsockname()
    start_server = lambda: netstring_server(server_socket)
    threading.Thread(target=start_server).start()

    # set up client
    def client_connect():
        clientsock = socket.create_connection((ip, port))
        client = NetstringSocket(clientsock)
        return client

    # connect, ping-pong
    client = client_connect()
    client.write_ns(b'ping')
    assert client.read_ns() == b'pong'
    s = time.time()
    for i in range(1000):
        client.write_ns(b'ping')
        assert client.read_ns() == b'pong'
    dur = time.time() - s
    print("netstring ping-pong latency", dur, "ms")

    s = time.time()
    for i in range(1000):
        client.write_ns(b'ping')
    resps = []
    for i in range(1000):
        resps.append(client.read_ns())
    e = time.time()
    assert all([r == b'pong' for r in resps])
    assert client.bsock.getrecvbuffer() == b''
    dur = e - s
    print("netstring pipelined ping-pong latency", dur, "ms")

    # tell the server to close the socket and then try a failure case
    client.write_ns(b'close')
    try:
        client.read_ns()
        raise Exception('read from closed socket')
    except ConnectionClosed:
        print("raised ConnectionClosed correctly")

    # test big messages
    client = client_connect()
    client.setmaxsize(128 * 1024)
    client.write_ns(b'reply128k')
    res = client.read_ns()
    assert len(res) == (128 * 1024)
    client.write_ns(b'close')

    # test that read timeouts work
    client = client_connect()
    client.settimeout(0.1)
    try:
        client.read_ns()
        raise Exception('did not timeout')
    except Timeout:
        print("read_ns raised timeout correctly")
    client.write_ns(b'close')

    # test that netstring max sizes work
    client = client_connect()
    client.setmaxsize(2048)
    client.write_ns(b'reply4k')
    try:
        client.read_ns()
        raise Exception('read more than maxsize')
    except NetstringMessageTooLong:
        print("raised MessageTooLong correctly")
    try:
        client.bsock.recv_until(b'b', maxsize=4096)
        raise Exception('recv_until did not raise MessageTooLong')
    except MessageTooLong:
        print("raised MessageTooLong correctly")
    assert client.bsock.recv_size(4097) == b'a' * 4096 + b','
    print('correctly maintained buffer after exception raised')

    # test BufferedSocket read timeouts with recv_until and recv_size
    client.bsock.settimeout(0.01)
    try:
        client.bsock.recv_until(b'a')
        raise Exception('recv_until did not raise Timeout')
    except Timeout:
        print('recv_until correctly raised Timeout')
    try:
        client.bsock.recv_size(1)
        raise Exception('recv_size did not raise Timeout')
    except Timeout:
        print('recv_size correctly raised Timeout')

    client.write_ns(b'shutdown')
    print("all passed")


def netstring_server_timeout_override(server_socket):
    """Netstring socket has an unreasonably low timeout,
    however it should be overridden by the `read_ns` argument."""

    try:
        while True:
            clientsock, addr = server_socket.accept()
            client = NetstringSocket(clientsock, timeout=0.01)
            while 1:
                request = client.read_ns(1)
                if request == b'close':
                    clientsock.close()
                    break
                elif request == b'shutdown':
                    return
                elif request == b'ping':
                    client.write_ns(b'pong')
    except Exception as e:
        print('netstring_server exiting with error: %r' % e)
        raise


def test_socketutils_netstring_timeout():
    """Tests that server socket timeout is overridden by the argument to read call.

    Server has timeout of 10 ms, and we will sleep for 20 ms. If timeout is not overridden correctly,
    a timeout exception will be raised."""

    print("running timeout test")

    # Set up server
    server_socket = socket.socket()
    server_socket.bind(('127.0.0.1', 0))  # localhost with ephemeral port
    server_socket.listen(100)
    ip, port = server_socket.getsockname()
    start_server = lambda: netstring_server_timeout_override(server_socket)
    threading.Thread(target=start_server).start()

    # set up client
    def client_connect():
        clientsock = socket.create_connection((ip, port))
        client = NetstringSocket(clientsock)
        return client

    # connect, ping-pong
    client = client_connect()
    time.sleep(0.02)
    client.write_ns(b'ping')
    assert client.read_ns() == b'pong'

    client.write_ns(b'shutdown')
    print("no timeout occurred - all good.")


def test_netstring_read_ns_timeout_covers_payload():
    # the read_ns timeout must apply to the payload and trailing
    # comma, not just the size prefix (the underlying BufferedSocket
    # defaults to a 10 second timeout)
    for partial in (b'5:hel', b'5:hello'):
        x, y = socket.socketpair()
        ns = NetstringSocket(x)
        y.sendall(partial)
        start = time.time()
        with pytest.raises(Timeout):
            ns.read_ns(timeout=0.05)
        assert time.time() - start < 2

class _TimeoutSock:
    "Minimal socket stand-in whose send/recv always time out."

    def gettimeout(self):
        return None

    def settimeout(self, timeout):
        self.timeout = timeout

    def send(self, data):
        raise socket.timeout()

    def recv(self, size):
        raise socket.timeout()

    def close(self):
        pass


def test_buffered_socket_constructor_defaults_and_overrides():
    x, y = socket.socketpair()
    # socketpair sockets have no timeout set, so the default applies
    assert x.gettimeout() is None
    bs = BufferedSocket(x)
    assert bs.timeout == 10
    assert bs.maxsize == 32 * 1024
    assert bs.gettimeout() == 10

    bs = BufferedSocket(x, timeout=None, maxsize=64, recvsize=3)
    assert bs.gettimeout() is None
    assert bs.maxsize == 64
    assert bs._recvsize == 3

    bs.setmaxsize(128)
    assert bs.maxsize == 128
    y.close()
    bs.close()


def test_send_and_recv_reject_nonzero_flags():
    x, y = socket.socketpair()
    bs = BufferedSocket(x)
    with pytest.raises(ValueError):
        bs.recv(1, flags=1)
    with pytest.raises(ValueError):
        bs.send(b'data', flags=1)
    y.close()
    bs.close()


def test_recv_uses_and_splits_internal_buffer():
    x, y = socket.socketpair()
    bs = BufferedSocket(x)

    # more buffered bytes than requested: keep the remainder
    bs.rbuf = b'abcdef'
    assert bs.recv(2) == b'ab'
    assert bs.getrecvbuffer() == b'cdef'

    # buffer smaller than requested but non-empty: drain it, don't block
    assert bs.recv(100) == b'cdef'
    assert bs.getrecvbuffer() == b''

    # an oversize socket recv is split over calls
    y.sendall(b'0123456789')
    assert bs.recv_size(3) == b'012'
    assert bs.getrecvbuffer() == b'3456789'
    assert bs.recv(4) == b'3456'
    assert bs.recv(3) == b'789'

    y.close()
    bs.close()


def test_recv_size_buffers_extra_and_honors_recvsize():
    x, y = socket.socketpair()
    bs = BufferedSocket(x, recvsize=4)
    y.sendall(b'hello')
    assert bs.recv_size(2) == b'he'
    assert bs.getrecvbuffer() == b'll'
    assert bs.recv_size(3) == b'llo'

    y.close()
    bs.close()


def test_peek_retains_bytes():
    x, y = socket.socketpair()
    bs = BufferedSocket(x)
    y.sendall(b'ping-pong')

    assert bs.peek(4) == b'ping'
    assert bs.getrecvbuffer() == b'ping-pong'
    assert bs.peek(2) == b'pi'
    assert bs.getrecvbuffer() == b'ping-pong'
    assert bs.recv_size(4) == b'ping'
    assert bs.getrecvbuffer() == b'-pong'

    y.close()
    bs.close()


def test_recv_close_defaults_and_too_long():
    x, y = socket.socketpair()
    bs = BufferedSocket(x)
    y.sendall(b'tail')
    y.close()
    # default maxsize path, connection closes so everything is returned
    assert bs.recv_close() == b'tail'
    bs.close()

    x, y = socket.socketpair()
    bs = BufferedSocket(x)
    y.sendall(b'abcde')
    with pytest.raises(MessageTooLong) as exc:
        bs.recv_close(maxsize=3)
    assert '3 bytes read' in str(exc.value)
    # all received bytes stay buffered, nothing is lost
    assert bs.getrecvbuffer() == b'abcde'
    y.close()
    bs.close()


def test_send_buffers_and_reports_bytes_sent():
    x, y = socket.socketpair()
    bx, by = BufferedSocket(x), BufferedSocket(y)
    by.buffer(b'foo')
    by.buffer(b'bar')
    assert by.getsendbuffer() == b'foobar'
    assert by.send(b'baz') == 9
    assert by.getsendbuffer() == b''
    assert bx.recv_size(9) == b'foobarbaz'

    # sendall is a passthrough
    by.sendall(b'!')
    assert bx.recv_size(1) == b'!'
    bx.close()
    by.close()


def test_send_and_recv_timeout_errors():
    bs = BufferedSocket(_TimeoutSock())
    with pytest.raises(Timeout) as exc:
        bs.send(b'abc')
    assert '3 bytes unsent' in str(exc.value)

    with pytest.raises(Timeout):
        bs.recv(1)

    with pytest.raises(Timeout):
        bs.recv_size(1)


def test_socket_option_passthroughs():
    x, y = socket.socketpair()
    bs = BufferedSocket(x)
    assert bs.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) == \
        x.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE)
    bs.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    assert x.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) == \
        bs.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE)
    y.close()
    bs.close()


def test_netstring_socket_accessors():
    x, y = socket.socketpair()
    ns = NetstringSocket(x)
    assert ns.fileno() == x.fileno()
    ns.settimeout(0.5)
    assert ns.timeout == 0.5
    ns.setmaxsize(1024)
    assert ns.maxsize == 1024
    assert ns._msgsize_maxsize == len('1024') + 1
    assert ns._calc_msgsize_maxsize(99) == 3
    y.close()
    ns.bsock.close()


def test_netstring_read_ns_with_explicit_maxsize():
    x, y = socket.socketpair()
    ns = NetstringSocket(x)
    y.sendall(b'3:abc,')
    assert ns.read_ns(maxsize=10) == b'abc'
    y.close()
    ns.bsock.close()


def test_netstring_invalid_size_prefix():
    x, y = socket.socketpair()
    ns = NetstringSocket(x)
    y.sendall(b'zz:abc,')
    with pytest.raises(NetstringInvalidSize) as exc:
        ns.read_ns()
    assert 'must be valid integer' in str(exc.value)
    y.close()
    ns.bsock.close()


def test_netstring_message_too_long_on_read_and_write():
    x, y = socket.socketpair()
    ns = NetstringSocket(x)
    y.sendall(b'999:')
    with pytest.raises(NetstringMessageTooLong) as exc:
        ns.read_ns(maxsize=100)
    assert '999 > 100' in str(exc.value)
    y.close()
    ns.bsock.close()

    x, y = socket.socketpair()
    ns = NetstringSocket(x, maxsize=3)
    with pytest.raises(NetstringMessageTooLong) as exc:
        ns.write_ns(b'abcd')
    assert '4 > 3' in str(exc.value)
    y.close()
    ns.bsock.close()


def test_netstring_missing_trailing_comma():
    x, y = socket.socketpair()
    ns = NetstringSocket(x)
    y.sendall(b'3:abcX')
    with pytest.raises(NetstringProtocolError) as exc:
        ns.read_ns()
    assert "expected trailing ','" in str(exc.value)
    y.close()
    ns.bsock.close()


def test_error_hierarchy_and_messages():
    assert issubclass(Error, socket.error)
    assert issubclass(ConnectionClosed, Error)
    assert issubclass(MessageTooLong, Error)
    assert issubclass(Timeout, socket.timeout)
    assert issubclass(NetstringProtocolError, Error)
    assert issubclass(NetstringInvalidSize, NetstringProtocolError)
    assert issubclass(NetstringMessageTooLong, NetstringProtocolError)

    assert str(MessageTooLong()) == 'message exceeded maximum size'
    msg = str(MessageTooLong(3, b'\n'))
    assert '3 bytes read' in msg
    assert "Delimiter not found: b'\\n'" in msg

    msg = str(Timeout(1.5, 'more'))
    assert 'socket operation timed out' in msg
    assert '1500.0ms' in msg
    assert msg.endswith('more')

    assert str(NetstringInvalidSize('bad')) == 'bad'


def test_recv_splits_single_oversize_socket_read():
    x, y = socket.socketpair()
    bs = BufferedSocket(x)
    y.sendall(b'abcdef')
    assert bs.recv(2) == b'ab'
    assert bs.getrecvbuffer() == b'cdef'
    y.close()
    bs.close()


def test_flush_sends_buffered_data():
    x, y = socket.socketpair()
    bx, by = BufferedSocket(x), BufferedSocket(y)
    by.buffer(b'held')
    assert by.getsendbuffer() == b'held'
    assert by.flush() is None
    assert by.getsendbuffer() == b''
    assert bx.recv_size(4) == b'held'
    bx.close()
    by.close()


def test_getsockopt_with_buflen():
    x, y = socket.socketpair()
    bs = BufferedSocket(x)
    expected = x.getsockopt(socket.SOL_SOCKET, socket.SO_LINGER, 8)
    assert bs.getsockopt(socket.SOL_SOCKET, socket.SO_LINGER, 8) == expected
    y.close()
    bs.close()
