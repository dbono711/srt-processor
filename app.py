import glob
import os
import time

import humanize
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
    [SRT](https://github.com/Haivision/srt/tree/master) flows.
    
    The user has the option to either upload a ```.pcap(ng)``` file containing 
    an SRT session for processing using the 
    [lib-tcpdump-processing](https://github.com/mbakholdina/lib-tcpdump-processing) 
    open source library, or spawning an ```srt-live-transmit``` process to receive a 
    flow. The ```SRT``` option requires a timeout to ensure it does not run indefinitely. 
    Once expired, the application will process statistics from the flow received. 
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
            output = pd.read_csv(
                f"pcaps/{os.path.splitext(file.name)[0]}.csv", delimiter=";"
            )
            st.subheader("lib-tcpdump-processing Results")
            analysis, charts = st.tabs(["Analysis", "Charts"])
            with analysis:
                col1, col2, col3 = st.columns(3)
                percentage_control_packets = (
                    output["srt.iscontrol"].sum() / len(output)
                ) * 100
                average_rtt = output["srt.rtt"].dropna().mean() / 1000

                col1.metric("Time", f"{output["_ws.col.cls_time"].iloc[-1]:.2f}s")
                col2.metric("Control Packets", f"{percentage_control_packets:.2f}%")
                col3.metric("Average RTT", f"{average_rtt:.2f}ms")

                st.write(libtcpdump_manager.get_output())

            with charts:
                # rtt chart
                rtt_data = output.copy()
                rtt_data["srt.rtt_ms"] = rtt_data["srt.rtt"] / 1000
                rtt_data["_ws.col.cls_time"] = pd.to_numeric(
                    rtt_data["_ws.col.cls_time"], errors="coerce"
                )
                rtt_data = rtt_data.dropna(subset=["_ws.col.cls_time", "srt.rtt_ms"])
                filtered_rtt = rtt_data[rtt_data["srt.rtt_ms"] < 100]
                rtt_chart = px.line(
                    filtered_rtt,
                    x="_ws.col.cls_time",
                    y="srt.rtt_ms",
                    template="seaborn",
                    title="Round Trip Time (RTT) over Time",
                    labels={"_ws.col.cls_time": "Time (s)", "srt.rtt_ms": "RTT (ms)"},
                )
                rtt_chart.update_layout(legend_title=None)
                st.plotly_chart(
                    rtt_chart, config={"displaylogo": False}, use_container_width=True
                )

                # bandwidth chart
                bw_data = output.copy()
                bw_data["srt.bw_mbps"] = bw_data["srt.bw"] / 1000
                bw_data["_ws.col.cls_time"] = pd.to_numeric(
                    bw_data["_ws.col.cls_time"], errors="coerce"
                )
                bw_data = bw_data.dropna(subset=["_ws.col.cls_time", "srt.bw_mbps"])
                bw_chart = px.line(
                    bw_data,
                    x="_ws.col.cls_time",
                    y="srt.bw_mbps",
                    template="seaborn",
                    title="Bandwidth (BW) over Time",
                    labels={"_ws.col.cls_time": "Time (s)", "srt.bw_mbps": "BW (Mbps)"},
                )
                bw_chart.update_layout(legend_title=None)
                st.plotly_chart(
                    bw_chart, config={"displaylogo": False}, use_container_width=True
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

    if os.path.exists("srt/received.ts.stats"):
        output = pd.read_csv("srt/received.ts.stats")
        st.subheader("_srt-live-transmit_ results")
        analysis, charts = st.tabs(["Analysis", "Charts"])

        with analysis:
            col1, col2, col3 = st.columns(3)
            col1.metric(
                "Total Bytes Received/Lost",
                f"{humanize.naturalsize(output["byteRecv"].iloc[-1])}/{humanize.naturalsize(output["byteRcvLoss"].iloc[-1])}",
            )
            col2.metric(
                "Average Round-Trip Time (RTT)", f"{output["msRTT"].mean():.2f} ms"
            )
            col3.metric(
                "Average Receive Rate",
                f"{output["mbpsRecvRate"].mean():.2f} Mbps",
            )

        # megabytes = bytes / (1024 ** 2)
        with charts:
            rtt_data = output.copy()
            rtt_data = rtt_data.dropna(subset=["Timepoint", "msRTT"])
            rtt_chart = px.line(
                rtt_data,
                x="Timepoint",
                y="msRTT",
                template="seaborn",
                title="Round Trip Time (RTT) over Time",
                labels={"Timepoint": "Time (s)", "msRTT": "RTT (ms)"},
            )
            rtt_chart.update_layout(legend_title=None)
            st.plotly_chart(
                rtt_chart, config={"displaylogo": False}, use_container_width=True
            )

            mbps_rcv_data = output.copy()
            mbps_rcv_data = mbps_rcv_data.dropna(subset=["Timepoint", "mbpsRecvRate"])
            mbps_rcv_chart = px.line(
                mbps_rcv_data,
                x="Timepoint",
                y="mbpsRecvRate",
                template="seaborn",
                title="Receive Rate over Time",
                labels={"Timepoint": "Time (s)", "mbpsRecvRate": "Rcv Rate (Mbps)"},
            )
            mbps_rcv_chart.update_layout(legend_title=None)
            st.plotly_chart(
                mbps_rcv_chart, config={"displaylogo": False}, use_container_width=True
            )

            # rtt_data = output.copy()
            # rtt_data = rtt_data.dropna(subset=["Timepoint", "msRTT", "mbpsRecvRate"])
            # filtered_rtt = rtt_data[rtt_data["msRTT"] < 100]

            # # Create the initial figure with msRTT
            # fig = px.line(
            #     filtered_rtt,
            #     x="Timepoint",
            #     y="msRTT",
            #     template="seaborn",
            #     title="Round Trip Time (RTT) and Receive Rate over Time",
            #     labels={"Timepoint": "Time (s)", "msRTT": "RTT (ms)"},
            # )

            # # Customize layout to include a secondary y-axis
            # fig.update_layout(
            #     yaxis=dict(
            #         title="RTT (ms)",
            #         titlefont=dict(color="#1f77b4"),
            #         tickfont=dict(color="#1f77b4"),
            #     ),
            #     yaxis2=dict(
            #         title="Receive Rate (Mbps)",
            #         titlefont=dict(color="#ff7f0e"),
            #         tickfont=dict(color="#ff7f0e"),
            #         anchor="x",
            #         overlaying="y",
            #         side="right",
            #     ),
            # )

            # # Add mbpsRecvRate to the figure using add_scatter
            # fig.add_scatter(
            #     x=filtered_rtt["Timepoint"],
            #     y=filtered_rtt["mbpsRecvRate"],
            #     mode="lines",
            #     name="Receive Rate (Mbps)",
            #     yaxis="y2",
            # )

            # # Display the chart in Streamlit
            # st.plotly_chart(
            #     fig, config={"displaylogo": False}, use_container_width=True
            # )

            # data = output.copy()
            # data = data.dropna(
            #     subset=["Timepoint", "byteRecv", "byteRcvLoss", "byteRcvDrop"]
            # )

            # # Create the initial figure with byteRecv
            # fig = px.line(
            #     data,
            #     x="Timepoint",
            #     y="byteRecv",
            #     template="seaborn",
            #     title="Bytes Received and Bytes Lost over Time",
            #     labels={"Timepoint": "Time (s)", "byteRecv": "Bytes Received"},
            # )

            # # Customize layout to include a secondary and tertiary y-axis
            # fig.update_layout(
            #     yaxis=dict(
            #         title="Bytes Received",
            #         titlefont=dict(color="#1f77b4"),
            #         tickfont=dict(color="#1f77b4"),
            #     ),
            #     yaxis2=dict(
            #         title="Bytes Lost",
            #         titlefont=dict(color="#ff7f0e"),
            #         tickfont=dict(color="#ff7f0e"),
            #         anchor="x",
            #         overlaying="y",
            #         side="right",
            #     ),
            # )

            # # Add byteRcvLoss to the figure using add_scatter
            # fig.add_scatter(
            #     x=data["Timepoint"],
            #     y=data["byteRcvLoss"],
            #     mode="lines",
            #     name="Bytes Lost",
            #     yaxis="y2",
            # )

            # # Display the chart in Streamlit
            # st.plotly_chart(
            #     fig, config={"displaylogo": False}, use_container_width=True
            # )
