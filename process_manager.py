import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional


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

    def check_for_valid_mpeg_ts(self) -> Optional[bool]:
        """
        Checks whether the specified file is a valid MPEG-TS (MPEG Transport Stream) format.

        This function uses `ffprobe` to analyze the format of the file located at "srt/received.ts".
        It returns `True` if the file is identified as an MPEG-TS format, `False` if not, and `None`
        if an error occurs during the process.

        Returns:
            Optional[bool]:
                - `True` if the file format is MPEG-TS.
                - `False` if the file format is not MPEG-TS or format information is missing.
                - `None` if an error occurs during the subprocess execution or JSON parsing.
        """
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_format",
                    "-of",
                    "json",
                    "srt/received.ts",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            output = json.loads(result.stdout)
            if "format" in output and "format_name" in output["format"]:
                if output["format"]["format_name"] == "mpegts":
                    return True

            return False

        except subprocess.CalledProcessError as e:
            self.logger.info(f"An error occurred while checking the file: {e}")
            return None
        except json.JSONDecodeError as e:
            self.logger.info(f"Failed to parse JSON output: {e}")
            return None

    def show_mpeg_ts_programs(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves the MPEG-TS (MPEG Transport Stream) programs from the specified file.

        This function uses `ffprobe` to extract program information from the file located at "srt/received.ts".
        It returns the program details in JSON format if available, or `None` if no programs are found or
        if an error occurs during the process.

        Returns:
            Optional[Dict[str, Any]]:
                - A dictionary containing the programs information if programs are found.
                - `None` if no programs are found or if an error occurs during the subprocess execution or JSON parsing.
        """
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_programs",
                    "-of",
                    "json",
                    "srt/received.ts",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            output = json.loads(result.stdout)
            if "programs" in output:
                return output

            return None

        except subprocess.CalledProcessError as e:
            self.logger.info(f"An error occurred while checking the file: {e}")
            return None
        except json.JSONDecodeError as e:
            self.logger.info(f"Failed to parse JSON output: {e}")
            return None

    def add_network_emulation(self, intf: str, delay: int) -> None:
        """
        Adds network emulation to a specified network interface using the `tc` (traffic control) command.

        This method applies a network delay to the specified interface by running a shell command that
        uses `tc` to add a network emulation (netem) rule. The delay is applied in milliseconds. If an
        error occurs during the process, it is logged.

        Args:
            intf (str): The name of the network interface to which the network emulation will be applied.
            delay (int): The delay in milliseconds to be added to the network interface.

        Returns:
            None
        """
        try:
            subprocess.run(
                [
                    "tc",
                    "qdisc",
                    "add",
                    "dev",
                    f"{intf}",
                    "root",
                    "netem",
                    "delay",
                    f"{delay}ms",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            self.logger.info(f"An error occurred while enabling network emulation: {e}")

    def clear_network_emulation(self, intf: str) -> None:
        """
        Removes network emulation from a specified network interface using the `tc` (traffic control) command.

        This method removes any network emulation rules (netem) applied to the specified interface by running
        a shell command that uses `tc`. If an error occurs during the process, it is logged.

        Args:
            intf (str): The name of the network interface from which the network emulation will be removed.

        Returns:
            None
        """
        try:
            subprocess.run(
                ["tc", "qdisc", "del", "dev", f"{intf}", "root", "netem"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            self.logger.info(f"An error occurred while removing network emulation: {e}")
