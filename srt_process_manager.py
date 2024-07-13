import subprocess
import threading


class SrtProcessManager:
    def __init__(self):
        self.process = None
        self.output = []

    def start_process(self, ip_address, timeout):
        command = f"srt-live-transmit srt://{ip_address}:{timeout}?mode=listener file://con > ./received.ts"
        self.process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.output = []

        threading.Thread(target=self.monitor_process_output).start()

    def monitor_process_output(self):
        if self.process is not None:
            for line in iter(self.process.stdout.readline, ""):
                self.output.append(line)
            self.process.stdout.close()

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
