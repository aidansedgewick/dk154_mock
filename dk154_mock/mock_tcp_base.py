#!/usr/bin/env python3

import logging
import time

import socket

import dk154_mock

logger = logging.getLogger("MockTCPBase")


def _DEFAULT_REPLY_CB(message):
    message = message.decode("utf-8")
    message = message.rstrip()
    return message + " ...echo!"


class MockTCPServer:

    TIMEOUT = 20.0

    def __init__(self, port=8888, reply_cb=_DEFAULT_REPLY_CB):
        self.PORT = port
        self.reply_cb = reply_cb

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def start(self):
        logger.info("start server")
        last_connection = time.time()

        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(180.0)
                sock.bind(("127.0.0.1", self.PORT))
                sock.listen(1)
                conn, addr = sock.accept()
                with conn:
                    logger.info(f"Connected to {addr}")
                    last_message = time.time()
                    print(last_message)

                    while True:
                        message = conn.recv(1024)
                        if not message:
                            logger.info("Received empty message. Server end.")
                            break
                        logger.info(f"Recieved message from {addr}")

                        try:
                            reply = self.reply_cb(message).encode("ascii")
                        except Exception as e:
                            logger.error(f"failed to respond to {message}. Send 'ERR'")
                            reply = "ERR".encode("ascii")
                        conn.sendall(reply)
            last_connection = time.time()
        logger.info("close server")


if __name__ == "__main__":
    with MockTCPServer() as server:
        server.start()
