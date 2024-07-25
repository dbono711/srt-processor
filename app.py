import glob
import os
import time

import pandas as pd
import plotly_express as px
import requests
import streamlit as st

from loggerfactory import LoggerFactory
from process_manager import LibTcpDumpManager, SrtProcessManager
from toolbox import Toolbox


@st.cache_resource
def get_toolbox():
    return Toolbox()


@st.cache_resource
def get_app_logger():
    return LoggerFactory.get_logger("app", log_level="WARNING")


@st.cache_resource
def get_libtcpdump_manager(_logger):
    return LibTcpDumpManager(_logger)


@st.cache_resource
def get_srt_process_manager(_logger):
    return SrtProcessManager(_logger)


st.set_page_config(page_title="SRT Processor", layout="wide")
st.title(":tv: SRT Processor")
st.subheader("Interactive application for presenting SRT session statistics")

toolbox = get_toolbox()
logger = get_app_logger()
libtcpdump_manager = get_libtcpdump_manager(logger)
srt_manager = get_srt_process_manager(logger)

_PUBLIC_IP = requests.get("https://api.ipify.org").content.decode("utf8")
_PRIVATE_IP = toolbox.get_primary_ip_address()

input_option = st.sidebar.selectbox(
    "Select an input method",
    ["SRT", "Packet Capture"],
    placeholder="Select option",
    index=None,
)

# packet capture
if input_option == "Packet Capture":
    st.markdown(
        """
        Upload a ```.pcap(ng)``` file containing an SRT session for processing using the 
        [lib-tcpdump-processing](https://github.com/mbakholdina/lib-tcpdump-processing) 
        open source library
        """
    )
    logger.info(f"User selected '{input_option}'")
    file = st.sidebar.file_uploader(
        "Packet capture containing an SRT stream",
        type=[".pcap", ".pcapng"],
        label_visibility="collapsed",
    )

    if file is not None:
        validated_file = toolbox.validate_pcap_file(file)

        if validated_file:
            logger.info("User successfully uploaded a valid capture file.")
            st.sidebar.success("Valid capture file detected.")

            # save uploaded file
            with open(f"./pcaps/{file.name}", "wb") as pcap:
                pcap.write(file.getbuffer())

            with st.spinner(f"Processing '{file.name}'"):
                libtcpdump_manager.start_process(file)
                time.sleep(15)

            logger.info(f"{file.name} processed successfully.")
            output = pd.read_csv(
                f"./pcaps/{os.path.splitext(file.name)[0]}.csv", delimiter=";"
            )

            analysis, charts = st.tabs(["Analysis", "Charts"])
            with analysis:
                col1, col2, col3 = st.columns(3)
                percentage_control_packets = (
                    output["srt.iscontrol"].sum() / len(output)
                ) * 100
                average_rtt = output["srt.rtt"].dropna().mean() / 1000

                col1.metric("Time", f"{output['_ws.col.Time'].iloc[-1]:.2f}s")
                col2.metric("Control Packets", f"{percentage_control_packets:.2f}%")
                col3.metric("Average RTT", f"{average_rtt:.2f}ms")

                st.write(libtcpdump_manager.get_output())

            with charts:
                # rtt chart
                rtt_data = output.copy()
                rtt_data["srt.rtt_ms"] = rtt_data["srt.rtt"] / 1000
                rtt_data["_ws.col.Time"] = pd.to_numeric(
                    rtt_data["_ws.col.Time"], errors="coerce"
                )
                rtt_data = rtt_data.dropna(subset=["_ws.col.Time", "srt.rtt_ms"])
                toolbox.draw_plotly_line_chart(
                    rtt_data,
                    x="_ws.col.Time",
                    y="srt.rtt_ms",
                    title="Round Trip Time (RTT) over Time",
                    labels={"_ws.col.Time": "Time (s)", "srt.rtt_ms": "RTT (ms)"},
                )

                # bw chart
                bw_data = output.copy()
                bw_data["srt.bw_mbps"] = bw_data["srt.bw"] / 1000
                bw_data["_ws.col.Time"] = pd.to_numeric(
                    bw_data["_ws.col.Time"], errors="coerce"
                )
                bw_data = bw_data.dropna(subset=["_ws.col.Time", "srt.bw_mbps"])
                toolbox.draw_plotly_line_chart(
                    bw_data,
                    x="_ws.col.Time",
                    y="srt.bw_mbps",
                    title="Bandwidth (BW) over Time",
                    labels={"_ws.col.Time": "Time (s)", "srt.bw_mbps": "BW (Mbps)"},
                )

        else:
            st.sidebar.error("Invalid capture file detected.")

# srt
if input_option == "SRT":
    st.markdown(
        """
        Spawn an [srt-live-transmit](https://github.com/Haivision/srt/blob/master/docs/apps/srt-live-transmit.md) 
        process to receive a flow. This application can function as either 
        ```listener``` or ```caller``` from a session handshake perspective, 
        but will always be the receiver from a session flow perspective.
        """
    )
    logger.info(f"User selected '{input_option}'")
    st.session_state.srt_connected = False

    with st.sidebar.container():
        st.warning("SRT Version: 1.5.3")
        submit_status = False

        srt_mode = st.radio(
            "Select connection mode",
            ["Caller", "Listener"],
            horizontal=True,
            help="""
            **Listener**: The 'agent' (this application) waits to be contacted by any peer caller.
            
            **Caller** (COMING SOON): The 'agent' (this application) sends the connection request to the peer, 
            which must be listener, and this way it initiates the connection.
            """,
        )

        if srt_mode == "Listener":
            srt_ip = ""
            st.warning(f"**Private IP:** {_PRIVATE_IP}")
            st.warning(f"**Public IP:** {_PUBLIC_IP}")
        else:  # srt_mode == "Caller"
            srt_ip = st.text_input(
                "IPv4 address of listener",
                help="Valid IPv4 address in dotted decimal notation (i.e., 192.168.1.7).",
                placeholder="Enter a valid IPv4 address",
            )

            if srt_ip:
                if not toolbox.validate_ipv4_address(srt_ip):
                    st.error(f"**{srt_ip}** is an invalid address")
                    submit_status = True

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
            help="""
            Timeout value for the SRT session, in seconds (30-600). A timeout
            is required to ensure the process does not run indefinitely.
            """,
        )

        submitted = st.button("Submit", disabled=submit_status)

    if srt_mode == "Listener":
        message = f"Listening on ```{_PRIVATE_IP}({_PUBLIC_IP}):{srt_port}```"
    else:  # srt_mode == "Caller"
        message = f"Attempting connectivity to ```{srt_ip}:{srt_port}```"

    if submitted:
        logger.info(f"User selected '{input_option}'")
        with st.spinner(message):
            srt_manager.start_process(
                mode=str(srt_mode).lower(),
                port=srt_port,
                timeout=srt_timeout,
                ip=srt_ip,
            )

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
                    result = srt_manager.extract_connected_ip_port()
                    connected.info(
                        f"Connected with ```{result[0][0]}:{result[0][1]}```"
                    )

                time.sleep(1)
                srt_timeout -= 1

            st.rerun()

    if os.path.exists("./srt/received.ts.stats"):
        if os.stat("./srt/received.ts.stats").st_size != 0:
            output = pd.read_csv("./srt/received.ts.stats")

            results, playback, raw_data = st.tabs(["Results", "Playback", "Raw Data"])
            with results:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Time", f"{output['Time'].iloc[-1] / 1000:.1f}s")
                col2.metric(
                    "Average Receive Rate",
                    f"{output['mbpsRecvRate'].mean():.2f}Mbps",
                )
                col3.metric(
                    "Average Round-Trip Time", f"{output['msRTT'].mean():.2f}ms"
                )
                col4.metric(
                    "Pkts Rcvd/Lost/Dropped/Retrans",
                    f"{output['pktRecv'].iloc[-1]}/\
                    {output['pktRcvLoss'].iloc[-1]}/\
                    {output['pktRcvDrop'].iloc[-1]}/\
                    {output['pktRcvRetrans'].iloc[-1]}",
                )

                with st.expander("Round-Trip Time (RTT)"):
                    st.write(
                        """
                        ```Round-Trip Time``` is a critical metric for measuring network latency, 
                        in this case in the context of an SRT session. It provides insights into 
                        the round-trip time for data packets, helping to monitor, troubleshoot, 
                        and optimize the performance of the network for real-time transmissions.

                        _**Low values:**_ Indicate a healthy and responsive network with minimal delays, 
                        ideal for real-time applications like live streaming.

                        _**High values:**_ Suggest higher latency and potential issues with the network
                        that could impact the quality of the transmission.
                        """
                    )
                    rtt_data = output.copy()
                    rtt_data = rtt_data.dropna(subset=["Timepoint", "msRTT"])
                    toolbox.draw_plotly_line_chart(
                        rtt_data,
                        x="Timepoint",
                        y="msRTT",
                        title="Round-Trip Time (RTT) over Time",
                        labels={
                            "Timepoint": "Time (s)",
                            "msRTT": "Round-Trip Time (ms)",
                        },
                    )

                with st.expander("Available Bandwidth & Receive Rate"):
                    st.write(
                        """
                        The ```Available Bandwidth``` indicates the maximum potential data transfer
                        rate that the network can support, while the ```Receive Rate``` shows the actual
                        rate at which data is being received.

                        _**Comparison of Capacity and Usage:**_ The ```Available Bandwidth``` value sets
                        the upper limit of what the network can handle, while the ```Receive Rate```
                        shows the actual usage of that capacity.

                        _**Performance Monitoring:**_ If the ```Receive Rate``` is consistently close to
                        the ```Available Bandwidth```, it suggests that the network is being fully utilized,
                        and there may be a risk of congestion or data loss if the demand increases further.
                        Conversely, if the ```Receive Rate``` is significantly lower than the
                        ```Available Bandwidth```, it might indicate underutilization of the network resources.
                        """
                    )

                    capacity_data = output.copy()
                    capacity_data = capacity_data.dropna(
                        subset=["Timepoint", "mbpsBandwidth", "mbpsRecvRate"]
                    )

                    capacity_data = capacity_data.melt(
                        id_vars=["Timepoint"],
                        value_vars=["mbpsBandwidth", "mbpsRecvRate"],
                        var_name="Metric",
                        value_name="Value",
                    )

                    capacity_data["Metric"] = capacity_data["Metric"].map(
                        {
                            "mbpsBandwidth": "Available Bandwidth",
                            "mbpsRecvRate": "Receive Rate",
                        }
                    )

                    toolbox.draw_plotly_line_chart(
                        capacity_data,
                        x="Timepoint",
                        y="Value",
                        title="Receive Rate and Available Bandwidth over Time",
                        color="Metric",
                        labels={"Timepoint": "Time (s)", "Value": "Mbps", "Metric": ""},
                    )

                with st.expander("Available Receive Buffer & Receive Buffer"):
                    st.write(
                        """
                        The ```Available Receive Buffer``` represents how much of the 
                        buffer's capacity remains available in terms of bytes, while the 
                        ```Receive Buffer``` provides context on the total 
                        buffer capacity in terms of time. Together, these metrics help in managing 
                        and optimizing buffer usage.

                        _**Indications:**_ A consistently high ```Available Receive Buffer``` value 
                        suggests that the buffer has plenty of available space, indicating efficient 
                        processing of incoming data, while ```Receive Buffer``` provides the 
                        understanding of how the buffer capacity in terms of time varies, which is useful 
                        for assessing the temporal aspects of buffering and processing delays.
                        """
                    )
                    buffer_data = output.copy()
                    buffer_data = buffer_data.dropna(
                        subset=["Timepoint", "byteAvailRcvBuf", "msRcvBuf"]
                    )
                    buffer_chart = px.line(
                        buffer_data,
                        x="Timepoint",
                        y="msRcvBuf",
                        template="seaborn",
                        title="Available Receive Buffer and Receive Buffer over Time",
                        labels={
                            "Timepoint": "Time (s)",
                            "msRcvBuf": "Receive Buffer (ms)",
                        },
                    )
                    buffer_chart.data[0].name = "Receive Buffer (ms)"
                    buffer_chart.data[0].showlegend = True

                    # Add byteAvailRcvBuf to the chart
                    buffer_chart.add_scatter(
                        x=buffer_data["Timepoint"],
                        y=buffer_data["byteAvailRcvBuf"],
                        mode="lines",
                        name="Available Receive Buffer (Bytes)",
                        yaxis="y2",
                        showlegend=True,
                    )

                    # Customize layout to include a secondary y-axis
                    buffer_chart.update_layout(
                        yaxis=dict(
                            title="Receive Buffer (ms)",
                            titlefont=dict(color="#1f77b4"),
                            tickfont=dict(color="#1f77b4"),
                        ),
                        yaxis2=dict(
                            title="Available Receive Buffer (Bytes)",
                            titlefont=dict(color="#ff7f0e"),
                            tickfont=dict(color="#ff7f0e"),
                            anchor="x",
                            overlaying="y",
                            side="right",
                        ),
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1,
                        ),
                    )

                    st.plotly_chart(
                        buffer_chart,
                        config={"displaylogo": False},
                        use_container_width=True,
                    )

                with st.expander("Packets Received, Lost, Dropped, & Retransmitted"):
                    st.write(
                        """
                        The ```Packets Received``` indicates the total number of packets successfully 
                        received by the receiver, the ```Received Packets Lost``` indicates the total 
                        number of packets that were expected but never received by the receiver, the 
                        ```Received Packets Dropped``` shows the number of packets that were received 
                        by the receiver but subsequently discarded, and the ```Received Packets Retransmitted```
                        represents the number of packets that were retransmitted and subsequently 
                        received by the receiver.
                        """
                    )
                    packet_data = output.copy()
                    packet_data = packet_data.dropna(
                        subset=[
                            "Timepoint",
                            "pktRecv",
                            "pktRcvLoss",
                            "pktRcvDrop",
                            "pktRcvRetrans",
                        ]
                    )

                    packet_data = packet_data.melt(
                        id_vars=["Timepoint"],
                        value_vars=[
                            "pktRecv",
                            "pktRcvLoss",
                            "pktRcvDrop",
                            "pktRcvRetrans",
                        ],
                        var_name="Metric",
                        value_name="Value",
                    )

                    packet_data["Metric"] = packet_data["Metric"].map(
                        {
                            "pktRecv": "Packets Received",
                            "pktRcvLoss": "Received Packets Lost",
                            "pktRcvDrop": "Received Packets Dropped",
                            "pktRcvRetrans": "Received Packets Retransmitted",
                        }
                    )

                    toolbox.draw_plotly_line_chart(
                        packet_data,
                        x="Timepoint",
                        y="Value",
                        color="Metric",
                        title="Packets Received, Lost, Dropped, & Retransmitted over Time",
                        labels={
                            "Timepoint": "Time (s)",
                            "Value": "Packets",
                            "Metric": "",
                        },
                    )

            with playback:
                if st.checkbox("Show captured video"):
                    if os.path.exists("./srt/received.mp4"):
                        video_file = open("./srt/received.mp4", "rb")
                        st.video(video_file)
                    else:
                        toolbox.convert_ts_to_mp4(
                            "./srt/received.ts", "./srt/received.mp4"
                        )
                        st.rerun()

            with raw_data:
                st.dataframe(output, use_container_width=True, hide_index=True)

        else:
            st.error("No SRT session statistics were created")

# cleanup all existing packet capture or srt output
if input_option is None:
    file_extensions = [
        "*.pcap",
        "*.csv",
        "*.processed",
        "*.ts",
        "*.log",
        "*.stats",
        "*.mp4",
    ]
    folders = ["./pcaps/", "./srt/"]
    for ext in file_extensions:
        for folder in folders:
            for file_path in glob.glob(os.path.join(folder, ext)):
                if os.path.exists(file_path):
                    os.remove(file_path)
