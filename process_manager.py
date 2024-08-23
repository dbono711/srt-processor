import os
import re
import subprocess
import threading
import time
from pathlib import Path


class ProcessManager:
    def __init__(self, logger) -> None:
        """
        Initialize the ProcessManager with a logger.

        Args:
            logger (logging.Logger): Logger instance for logging process events.
        """
        self.logger = logger
        self.process = None

    def check_if_running(self) -> bool:
        """
        Check if the process is currently running.

        Returns:
            bool: True if the process is running, False otherwise.
        """
        if self.process:
            return self.process.poll() is None
        return False

    def stop_process(self) -> None:
        """
        Stop the process if it is currently running.

        If the process is running, it will be terminated, and a log message will be recorded.

        Returns:
            None
        """
        if self.process and self.check_if_running():
            self.process.terminate()
            self.logger.info("Process terminated.")


class LibTcpDumpManager(ProcessManager):
    def __init__(self, logger) -> None:
        """
        Initialize the LibTcpDumpManager with a logger.

        Args:
            logger (logging.Logger): Logger instance for logging process events.
        """
        super().__init__(logger)
        self.results_path = "./pcaps/result.processed"

    def start_process(self, file: Path) -> None:
        """
        Start the tcpdump processing using the specified file.

        Args:
            file (Path): The file to be processed.

        Returns:
            None
        """
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

    def get_output(self) -> str:
        """
        Retrieve the output from the processed results file, trimming the first two lines.

        Returns:
            str: The processed and trimmed output from the results file.
        """
        with open(self.results_path, "r") as results:
            result_lines = results.readlines()
            trimmed_results = "".join(result_lines[2:])

        return trimmed_results

    def redirect_output_to_file(self) -> None:
        """
        Redirect the stdout of the subprocess to a specified results file.

        This method continuously reads lines from the process's stdout and writes them to the results file.

        Returns:
            None
        """
        with open(self.results_path, "w") as results:
            if self.process:
                for line in iter(self.process.stdout.readline, ""):
                    results.write(line)
                self.process.stdout.close()


class SrtProcessManager(ProcessManager):
    def __init__(self, logger) -> None:
        """
        Initialize the SrtProcessManager with a logger.

        Args:
            logger (logging.Logger): Logger instance for logging process events.
        """
        super().__init__(logger)
        self.connection_established = False

    def start_process(
        self, version: str, mode: str, port: int, timeout: int, ip: str
    ) -> None:
        """
        Start the SRT process using the given parameters.

        Args:
            version (str): Version of the SRT tool to use.
            mode (str): The mode to use for the SRT connection (e.g., 'listener' or 'caller').
            port (int): The port number to connect to.
            timeout (int): The timeout for the connection in milliseconds.
            ip (str): The IP address to connect to.

        Returns:
            None
        """
        command = (
            f"srt-live-transmit-v{version} -fullstats -statspf:csv -stats-report-frequency:100 "
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

    def monitor_connection_status(self) -> None:
        """
        Monitor the status of the SRT connection by checking the size of the stats file.
        If the file is non-empty, the connection is considered established.

        Returns:
            None
        """
        time.sleep(1)
        while self.process.poll() is None:
            if os.stat("./srt/received.ts.stats").st_size != 0:
                self.connection_established = True
                break
            time.sleep(1)

    def extract_connected_ip_port(self) -> str:
        """
        Extract the connected IP address and port from the log file.

        Returns:
            str: The connected IP address and port in the format "IP:Port".
            Returns "error: unable to determine connected host" if not found.
        """
        pattern = r"(\d+\.\d+\.\d+\.\d+):(\d+)"

        with open("./srt/received.ts.log", "r") as log:
            log_content = log.read()
            match = re.search(pattern, log_content)

            if match:
                return f"{match.group(1)}:{match.group(2)}"
            else:
                return "error: unable to determine connected host"

    def get_connection_status(self) -> bool:
        """
        Get the current status of the SRT connection.

        Returns:
            bool: True if the connection is established, False otherwise.
        """
        return self.connection_established
