import os
import re
import subprocess
import threading
import time


class ProcessManager:
    def __init__(self, logger):
        self.logger = logger
        self.process = None

    def check_if_running(self):
        if self.process:
            return self.process.poll() is None
        return False

    def stop_process(self):
        if self.process and self.check_if_running():
            self.process.terminate()
            self.logger.info("Process terminated.")


class LibTcpDumpManager(ProcessManager):
    def __init__(self, logger):
        super().__init__(logger)
        self.results_path = "./pcaps/result.processed"

    def start_process(self, file):
        command = f"get-traffic-stats --overwrite --side rcv pcaps/{file.name}"
        self.logger.info(f"Starting process with '{command}'")
        self.process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        threading.Thread(target=self.redirect_output_to_file).start()

    def get_output(self):
        with open(self.results_path, "r") as results:
            result_lines = results.readlines()
            trimmed_results = "".join(result_lines[2:])

        return trimmed_results

    def redirect_output_to_file(self):
        with open(self.results_path, "w") as results:
            if self.process:
                for line in iter(self.process.stdout.readline, ""):
                    results.write(line)
                self.process.stdout.close()


class SrtProcessManager(ProcessManager):
    def __init__(self, logger):
        super().__init__(logger)
        self.connection_established = False

    def start_process(self, mode, port, timeout, ip):
        command = (
            f"srt-live-transmit -fullstats -statspf:csv -stats-report-frequency:100 "
            f"-statsout:srt/received.ts.stats -loglevel:info -logfile:srt/received.ts.log "
            f"-to:{timeout} srt://{ip}:{port}?mode={mode} file://con > srt/received.ts"
        )
        self.logger.info(f"Starting process with '{command}'")
        self.process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        threading.Thread(target=self.monitor_connection_status).start()

    def monitor_connection_status(self):
        time.sleep(1)
        while self.process.poll() is None:
            if os.stat("./srt/received.ts.stats").st_size != 0:
                self.connection_established = True
                break
            time.sleep(1)

    def extract_connected_ip_port(self):
        pattern = r"from peer @\d+ \((\d+\.\d+\.\d+\.\d+:\d+)\)"

        with open("./srt/received.ts.log", "r") as log:
            match = re.search(pattern, log.read())
            if match:
                return match.group(1)
            else:
                return "error: unable to determine connected host"

    def get_connection_status(self):
        return self.connection_established
