import re
import subprocess
import threading
import time


class SrtProcessManager:
    def __init__(self, logger):
        self.logger = logger
        self.process = None
        self.output = []
        self.connection_established = False

    def start_process(self, mode, port, timeout):
        command = f"srt-live-transmit -fullstats -statspf:csv -stats-report-frequency:1000 -statsout:srt/received.ts.stats -loglevel:info -logfile:srt/received.ts.log -to:{timeout} srt://0.0.0.0:{port}?mode={mode} file://con > srt/received.ts"
        self.logger.info(f"Starting process with '{command}'")
        self.process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        threading.Thread(target=self.monitor_process_output).start()
        threading.Thread(target=self.monitor_connection_status).start()

    def monitor_process_output(self):
        if self.process is not None:
            for line in iter(self.process.stdout.readline, ""):
                self.output.append(line)
            self.process.stdout.close()

    def monitor_connection_status(self):
        time.sleep(1)
        while self.process.poll() is None:
            with open("srt/received.ts.log", "r") as log_file:
                logs = log_file.read()
                if re.search(r"managed", logs):
                    self.connection_established = True
                    break
            time.sleep(1)

    def check_if_running(self):
        if self.process is not None:
            return self.process.poll() is None
        return False

    def stop_process(self):
        if self.process is not None:
            self.process.terminate()
            self.process.wait()

    def get_output(self):
        return "".join(self.output)

    def extract_ip_port(self):
        pattern = r"(\d+\.\d+\.\d+\.\d+):(\d+)"

        with open("srt/received.ts.log", "r") as log:
            matches = re.findall(pattern, log.read())

            result = {(match[0], match[1]) for match in matches}

            return list(result)

    def get_connection_status(self):
        return self.connection_established
