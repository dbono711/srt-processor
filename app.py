import glob
import os
import time

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from libtcpdump_process_manager import LibTcpDumpManager
from loggerfactory import LoggerFactory
from srt_process_manager import SrtProcessManager

_PUBLIC_IP = requests.get("https://api.ipify.org").content.decode("utf8")


@st.cache_resource(max_entries=10)
def _logger():
    return LoggerFactory.get_logger("app.py", log_level="WARNING")


@st.cache_resource(max_entries=10)
def _srt_manager(_logger):
    return SrtProcessManager(_logger)


@st.cache_resource(max_entries=10)
def _libtcpdump_manager(_logger):
    return LibTcpDumpManager(_logger)


st.set_page_config(page_title="SRT Processor", layout="wide")
st.title(":tv: SRT Processor")
st.markdown(
    """
    Interactive application for presenting various statistics about 
    [SRT](https://github.com/Haivision/srt/tree/master) flows derived 
    from packet captures. The user has the option to either upload a 
    ```.pcap(ng)``` file for direct processing, or spawn an SRT session 
    to receive a stream. The application uses the 
    [lib-tcpdump-processing](https://github.com/mbakholdina/lib-tcpdump-processing) 
    open source library for creating the statistics. When using the ```SRT``` option, 
    additional statistics from the SRT session are also presented.

    👈 Select an input method to get started.
    """
)

logger = _logger()
srt_manager = _srt_manager(logger)
libtcpdump_manager = _libtcpdump_manager(logger)

input_option = st.sidebar.selectbox(
    "Select an input method",
    ["SRT", "Packet Capture"],
    placeholder="Select option",
    index=None,
)

if input_option == "Packet Capture":
    file = st.sidebar.file_uploader(
        "Packet capture containing an SRT stream",
        type=[".pcap", ".pcapng"],
        label_visibility="collapsed",
    )

    if file is not None:
        validated_file = libtcpdump_manager.validate_pcap_file(file)

        if validated_file:
            logger.info("User successfully uploaded a valid capture file.")
            st.sidebar.success("Valid capture file detected.")
            with open(f"pcaps/{file.name}", "wb") as pcap:
                pcap.write(file.getbuffer())

            with st.spinner(f"Processing {file.name}"):
                libtcpdump_manager.process_tcpdump(file)
                time.sleep(15)

            logger.info(f"{file.name} processed successfully.")
            results, analysis = st.tabs(["Results", "Charts"])
            output = pd.read_csv(
                f"pcaps/{os.path.splitext(file.name)[0]}.csv", delimiter=";"
            )

            with results:
                col1, col2, col3 = st.columns(3)
                percentage_control_packets = (
                    output["srt.iscontrol"].sum() / len(output)
                ) * 100
                average_rtt = output["srt.rtt"].dropna().mean() / 1000

                col1.metric(
                    "Session Time", f"{output["_ws.col.cls_time"].iloc[-1]:.2f}s"
                )
                col2.metric("Control Packets", f"{percentage_control_packets:.2f}%")
                col3.metric("Average RTT", f"{average_rtt:.2f}ms")

                st.write(libtcpdump_manager.get_output())

            with analysis:
                # rtt chart
                output["srt.rtt_ms"] = output["srt.rtt"] / 1000
                output["_ws.col.cls_time"] = pd.to_numeric(
                    output["_ws.col.cls_time"], errors="coerce"
                )
                output = output.dropna(subset=["_ws.col.cls_time", "srt.rtt_ms"])
                filtered_output = output[output["srt.rtt_ms"] < 100]
                chart = px.line(
                    filtered_output,
                    x="_ws.col.cls_time",
                    y="srt.rtt_ms",
                    template="seaborn",
                    title="Round Trip Time (RTT) over Time",
                    labels={"_ws.col.cls_time": "Time (s)", "srt.rtt_ms": "RTT (ms)"},
                )
                chart.update_layout(legend_title=None)
                st.plotly_chart(
                    chart, config={"displaylogo": False}, use_container_width=True
                )

                # bandwidth chart
                output["srt.bw_mbps"] = output["srt.bw"] / 1000
                output["_ws.col.cls_time"] = pd.to_numeric(
                    output["_ws.col.cls_time"], errors="coerce"
                )
                output = output.dropna(subset=["_ws.col.cls_time", "srt.bw_mbps"])
                chart = px.line(
                    output,
                    x="_ws.col.cls_time",
                    y="srt.bw_mbps",
                    template="seaborn",
                    title="Bandwidth (BW) over Time",
                    labels={"_ws.col.cls_time": "Time (s)", "srt.bw_mbps": "BW (Mbps)"},
                )
                chart.update_layout(legend_title=None)
                st.plotly_chart(
                    chart, config={"displaylogo": False}, use_container_width=True
                )

        else:
            st.sidebar.error("Invalid capture file detected.")

    else:
        file_extensions = ["*.pcap", "*.csv"]
        for ext in file_extensions:
            for file_path in glob.glob(os.path.join("pcaps/", ext)):
                if os.path.exists(file_path):
                    os.remove(file_path)

if input_option == "SRT":
    st.session_state.srt_connected = False

    with st.sidebar.form("SRT"):
        srt_mode = st.radio(
            "Select connection mode",
            ["Listener"],
            horizontal=True,
            help="""
            **Listener**: The 'agent' (this application) waits to be contacted by any peer \
            caller.

            **Caller** (COMING SOON): The 'agent' (this application) sends the connection \
            request to the peer, which must be listener, and this way it \
            initiates the connection
            """,
        )

        if srt_mode == "Listener":
            st.warning(f"**IP Address:** {_PUBLIC_IP}")
            srt_port = st.number_input(
                "Select port",
                min_value=9000,
                max_value=9100,
                value=9000,
                step=1,
                format="%d",
                help="Port for the SRT session (9000-9100).",
            )

        srt_timeout = st.number_input(
            "Select timeout",
            min_value=30,
            max_value=600,
            value=60,
            step=1,
            format="%d",
            help="Timeout value for the SRT session, in seconds (30-600).",
        )
        submitted = st.form_submit_button("Submit")

    if submitted:
        with st.spinner(f"Listening on ```{_PUBLIC_IP}:{srt_port}```"):
            srt_manager.start_process(str(srt_mode).lower(), srt_port, srt_timeout)

            counter = st.empty()
            connected = st.empty()
            while srt_timeout > 0:
                counter.info(f"SRT session expires in ```{srt_timeout}``` seconds")

                if st.session_state.srt_connected:
                    time.sleep(1)
                    srt_timeout -= 1
                    continue

                if srt_manager.get_connection_status():
                    st.session_state.srt_connected = True
                    result = srt_manager.extract_ip_port()
                    connected.info(
                        f"Connected with ```{result[0][0]}:{result[0][1]}```"
                    )

                time.sleep(1)
                srt_timeout -= 1

            st.rerun()
