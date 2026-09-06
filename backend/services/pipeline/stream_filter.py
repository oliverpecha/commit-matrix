#!/usr/bin/env python3
"""Cleans container stdout, triggers interactive UI, and writes a plain-text log."""
import sys
import re
import signal
import os

muted = False
muted_buffer = []

def un_mute_handler(signum, frame):
    global muted, muted_buffer
    if muted:
        sys.stdout.write("\n── Replaying log from the start ──\n")
        for line in muted_buffer:
            sys.stdout.write(line)
        sys.stdout.write("── Now following live ──\n")
        sys.stdout.flush()
        muted = False
        muted_buffer.clear()

signal.signal(signal.SIGUSR1, un_mute_handler)

def _sigint_handler(signum, frame):
    sys.exit(130)
signal.signal(signal.SIGINT, _sigint_handler)

ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
NOISE_RE = re.compile(r'^\s*(\*\s*|\[entrypoint\].*)$')

def main():
    global muted, muted_buffer
    log_path = sys.argv[1] if len(sys.argv) > 1 else "/dev/null"
    
    owner = os.environ.get("HOST_REPO_OWNER", "unknown")
    repo = os.environ.get("HOST_REPO_NAME", "unknown")
    token = os.environ.get("MATRIX_TOKEN", "unknown")
    server_ip = os.environ.get("SERVER_IP", "localhost")

    banner = f"""
📊 Live Commit-Matrix Dashboard:
═══════════════════════════════════════════════════════════════════════════
 🏠 Local:  http://localhost:8000/?owner={owner}&repo={repo}&token={token}
 ☁️  Server: http://{server_ip}:8000/?owner={owner}&repo={repo}&token={token}
═══════════════════════════════════════════════════════════════════════════

  Feel free to open the browser now — the engine keeps scoring in the
  background regardless of what you do here.

  [Enter]  Show terminal streaming from the start, then follow live
  [q]      Stop the engine now (progress already made is preserved)
"""

    with open(log_path, "w", buffering=1) as log_file:
        current_line = ""
        in_traceback = False
        traceback_buf = []

        while True:
            char = sys.stdin.read(1)
            if not char:
                if current_line:
                    if not muted: sys.stdout.write(current_line)
                    log_file.write(ANSI_RE.sub('', current_line))
                break

            current_line += char

            # Handle carriage returns (progress bar animation)
            if char == '\r':
                if "Asynchronous scoring engine starting up" in current_line:
                    sys.stdout.write(banner)
                    sys.stdout.flush()
                    muted = True
                    current_line = ""
                    continue
                
                # If muted, we ignore \r updates entirely so they don't bloat the replay buffer
                if not muted:
                    sys.stdout.write(current_line)
                    sys.stdout.flush()
                current_line = ""

            # Handle newlines (completed output segments)
            elif char == '\n':
                if "Asynchronous scoring engine starting up" in current_line:
                    if not muted:
                        sys.stdout.write(banner)
                        sys.stdout.flush()
                        muted = True
                    current_line = ""
                    continue

                if NOISE_RE.match(current_line.rstrip('\n')):
                    current_line = ""
                    continue

                if current_line.startswith("Traceback (most recent call last):"):
                    in_traceback = True
                    traceback_buf = [current_line]
                    current_line = ""
                    continue

                if in_traceback:
                    traceback_buf.append(current_line)
                    if current_line.strip() and not current_line.startswith((" ", "\t")):
                        complete_tb = "".join(traceback_buf)
                        if not muted:
                            sys.stdout.write(complete_tb)
                            sys.stdout.flush()
                        else:
                            muted_buffer.append(complete_tb)
                        in_traceback = False
                        traceback_buf = []
                    current_line = ""
                    continue

                if not muted:
                    sys.stdout.write(current_line)
                    sys.stdout.flush()
                else:
                    muted_buffer.append(current_line)

                clean = ANSI_RE.sub('', current_line)
                log_file.write(clean)
                current_line = ""

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except BrokenPipeError:
        sys.exit(0)
