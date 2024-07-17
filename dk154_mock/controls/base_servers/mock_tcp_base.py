import logging
import time
import traceback
import socket

import dk154_mock

logger = logging.getLogger("MockTCPBase")


def _DEFAULT_REPLY_CB(message):
    message = message.decode("utf-8")
    message = message.rstrip()
    return message + " ...echo!"


class MockTCPServer:

    # TIMEOUT = 20.0

    def __init__(
        self, port=8888, reply_cb=_DEFAULT_REPLY_CB, timeout=180.0, server_name=None
    ):
        self.PORT = port
        self.reply_cb = reply_cb

        self.timeout = timeout

        cb_name = reply_cb.__name__
        self.server_name = server_name
        logger.info(
            f"init MockTCPServer {self.server_name} with:\n    port={port}, callback={cb_name}"
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        logger.info(f"exit MockTCPServer {self.server_name}")
        pass

    def start(self):
        logger.info(f"start server {self.server_name}")
        last_connection = time.time()

        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                sock.bind(("127.0.0.1", self.PORT))
                sock.listen(1)
                conn, addr = sock.accept()
                with conn:
                    logger.info(f"Connected to {addr}")

                    while True:
                        message = conn.recv(1024)
                        if not message:
                            logger.info(
                                f"({self.server_name}): received empty message. Server end."
                            )
                            break
                        msg = f"({self.server_name}): recieved message from {addr}"
                        logger.info(msg)

                        try:
                            reply = self.reply_cb(message).encode("ascii")
                        except Exception as e:
                            tr = traceback.format_exc()
                            logger.info(f"last exception:\n\n{tr}")

                            logger.error(f"failed to respond to {message}. Send 'ERR'")
                            reply = "ERR".encode("ascii")
                        conn.sendall(reply)
            last_connection = time.time()
        logger.info("close server")


if __name__ == "__main__":

    with MockTCPServer() as server:
        server.start()
