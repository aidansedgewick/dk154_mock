import logging
import time
import threading
import traceback
import socket
from argparse import ArgumentParser

import dk154_control


logger = logging.getLogger("MockTCPBase")


def _DEFAULT_REPLY_CB(message):
    message = message.decode("utf-8")
    message = message.rstrip()
    return message.upper() + " ...echo!"


class MockTCPServer:

    # TIMEOUT = 20.0

    def __init__(
        self, port=8888, reply_cb=_DEFAULT_REPLY_CB, timeout=600.0, server_name=None
    ):
        self.PORT = port
        self.reply_cb = reply_cb

        self.timeout = timeout

        cb_name = reply_cb.__name__
        self.server_name = server_name or "MockTCPServer"
        logger.info(
            f"init MockTCPServer '{self.server_name}' with:\n    "
            f"port={port}, callback={cb_name}, timeout={timeout:.1f}sec"
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        logger.info(f"safe exit MockTCPServer {self.server_name}")
        pass

    def accept_new_client(self, conn, addr):
        with conn:
            logger.info(f"Connected to {addr}")

            while True:
                message = conn.recv(1024)
                if not message:
                    logger.info(
                        f"({self.server_name}): received empty message. Server end."
                    )
                    break
                msg = f"({self.server_name}): recieved from {addr}"
                logger.info(msg)

                try:
                    reply = self.reply_cb(message).encode("ascii")
                except Exception as e:
                    tr = traceback.format_exc()
                    logger.info(f"last exception:\n\n{tr}")

                    logger.error(f"failed to respond to {message}. Send 'ERR'")
                    reply = "ERR".encode("ascii")
                conn.sendall(reply)

    def listen_to_connection(self, conn, addr):
        with conn:
            logger.debug(f"Connected to {addr}")

            addr_str = f"{addr[0]}:{addr[1]}"

            while True:
                message = conn.recv(1024)
                if not message:
                    logger.debug(
                        f"({self.server_name}): recv empty {addr_str} - close conn."
                    )
                    break
                msg = f"({self.server_name}): recv from {addr_str}"
                logger.debug(msg)

                try:
                    reply = self.reply_cb(message).encode("ascii")
                except Exception as e:
                    tr = traceback.format_exc()
                    logger.info(f"last exception:\n\n{tr}")

                    logger.error(f"failed to respond to {message}. Send 'ERR'")
                    reply = "ERR".encode("ascii")
                conn.sendall(reply)

    def start(self):
        logger.info(f"start server {self.server_name} (port={self.PORT})")
        last_connection = 0.0  # time.time()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(self.timeout)
            # sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", self.PORT))
            sock.listen(0)
            logger.info(f"{self.server_name} start socket")
            while True:
                conn, addr = sock.accept()
                thread = threading.Thread(
                    target=self.listen_to_connection, args=(conn, addr)
                )
                thread.start()

            last_connection = time.time()
        logger.info("close server")


def server_in_context(*args, **kwargs):
    with MockTCPServer(*args, **kwargs) as server:
        server.start()


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("-p", "--port", default=8888, type=int)
    args = parser.parse_args()

    # with MockTCPServer(port=args.port) as server:
    #    server.start()

    server_thread = threading.Thread(
        target=server_in_context, kwargs=dict(port=args.port)
    )
    server_thread.name = "server_thread"
    server_thread.start()
