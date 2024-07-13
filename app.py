import time

import pandas as pd
import streamlit as st

from libtcpdump_process_manager import LibTcpDumpManager
from loggerfactory import LoggerFactory
from srt_process_manager import SrtProcessManager

srt_manager = SrtProcessManager()
libtcpdump_manager = LibTcpDumpManager()
logger = LoggerFactory.get_logger("app.py", log_level="WARNING")

st.set_page_config(page_title="SRT Processor", page_icon=":tv:", layout="wide")
st.title(":tv: SRT Processor")

with st.expander("Overview", expanded=True):
    st.markdown(
        """
        **SRT Processor** is an interactive web application for presenting
        various statistics about [SRT](https://github.com/Haivision/srt/tree/master)
        flows derived from packet captures. The user has the option to either upload a
        ```.pcap(ng)``` file for direct processing, or spawn an SRT session to receive
        a stream. The application uses the [lib-tcpdump-processing](https://github.com/mbakholdina/lib-tcpdump-processing)
        open source library for creating the statistics. If using the ```SRT``` option,
        additional logs and statistics from the SRT session are also presented.

        👈 Select an input method to get started.
        """
    )

input_option = st.sidebar.selectbox(
    "Select an input method",
    ["SRT", "Packet Capture"],
    placeholder="Select",
    index=None,
)

if input_option == "Packet Capture":
    file = st.sidebar.file_uploader(
        "Upload a valid ```.pcap``` or ```.pcapng``` file containing an SRT stream",
        type=[".pcap", ".pcapng"],
    )

    if file is not None:
        validated_file = libtcpdump_manager.validate_pcap_file(file)
        if validated_file:
            logger.info("User successfully uploaded a valid file.")
            with open("pcaps/output.pcap", "wb") as pcap:
                pcap.write(file.getbuffer())

            st.sidebar.success("Valid file uploaded.")

            with st.spinner(f"Processing {file.name}"):
                libtcpdump_manager.process_tcpdump()
                time.sleep(10)

            results, analysis = st.tabs(["Results", "Analysis"])
            results.write(libtcpdump_manager.get_output())
            output = pd.read_csv(
                "pcaps/output.csv",
                delimiter=";",
                usecols=[
                    "_ws.col.cls_time",
                    "_ws.col.protocol",
                    "_ws.col.def_src",
                    "_ws.col.def_dst",
                ],
            )
            analysis.dataframe(output.head(20))

        else:
            st.sidebar.error(
                "The uploaded file is not a valid ```.pcap``` or ```.pcapng``` file."
            )

if input_option == "SRT":
    with st.sidebar.form("SRT"):
        srt_mode = st.radio("Select mode", ["Listener", "Caller"], horizontal=True)

        submitted = st.form_submit_button("Submit")
        if submitted:
            st.write(srt_mode)

# ip = requests.get("https://api.ipify.org").content.decode("utf8")
# print("My public IP address is: {}".format(ip))
