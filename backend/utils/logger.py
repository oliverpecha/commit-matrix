#!/usr/bin/env python3
import os

class DualLogger:
    """Handles real-time duplication of stdout/stderr to disk without buffering delays."""
    def __init__(self, terminal_stream, file_path):
        self.terminal = terminal_stream
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        self.log_file = open(file_path, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)
        self.flush()

    def flush(self):
        self.terminal.flush()
        if self.log_file and not self.log_file.closed:
            self.log_file.flush()

    def close(self):
        if self.log_file and not self.log_file.closed:
            self.log_file.close()
