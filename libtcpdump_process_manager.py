import subprocess
import threading


class LibTcpDumpManager:
    def __init__(self):
        self.process = None
        self.results_path = "./pcaps/output.processed"

    def process_tcpdump(self):
        command = "/home/ubuntu/lib-tcpdump-processing/.venv/bin/get-traffic-stats --side rcv pcaps/output.pcap"
        self.process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        threading.Thread(target=self.redirect_output_to_file).start()

    def redirect_output_to_file(self):
        with open(self.results_path, "w") as results:
            if self.process is not None:
                for line in iter(self.process.stdout.readline, ""):
                    results.write(line)
                self.process.stdout.close()

    def check_if_running(self):
        if self.process is not None:
            return self.process.poll() is None

        return False

    def get_output(self):
        with open(self.results_path, "r") as results:
            next(results)

            return results.read()

    def validate_pcap_file(self, file):
        pcap_magic_numbers = [
            b"\xd4\xc3\xb2\xa1",
            b"\xa1\xb2\xc3\xd4",
            b"\x4d\x3c\xb2\xa1",
            b"\xa1\xb2\x3c\x4d",
        ]
        pcapng_magic_number = b"\x0a\x0d\x0d\x0a"

        try:
            magic_number = file.read(4)
            if (
                magic_number in pcap_magic_numbers
                or magic_number == pcapng_magic_number
            ):
                return True
            else:
                return False
        except Exception as e:
            print(f"Error reading file: {e}")
            return False
