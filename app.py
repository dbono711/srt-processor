import glob
import os
import time
from typing import Any, List, Optional, Tuple

import netifaces
import pandas as pd
import plotly_express as px
import streamlit as st
from streamlit import runtime

from loggerfactory import LoggerFactory
from process_manager import LibTcpDumpManager, SrtProcessManager
from toolbox import Toolbox


@st.cache_resource
def get_toolbox() -> Toolbox:
    """
    Retrieve a cached instance of the Toolbox.

    Returns:
        Toolbox: An instance of the Toolbox class.
    """
    return Toolbox()


@st.cache_resource
def get_app_logger() -> LoggerFactory:
    """
    Retrieve a cached instance of the application logger.

    Returns:
        Logger: A logger instance with the name 'app' and log level 'WARNING'.
    """
    return LoggerFactory.get_logger("app", log_level="WARNING")


@st.cache_resource
def get_libtcpdump_manager(_logger) -> LibTcpDumpManager:
    """
    Retrieve a cached instance of the LibTcpDumpManager.

    Args:
        _logger (Logger): Logger instance to be used by LibTcpDumpManager.

    Returns:
        LibTcpDumpManager: An instance of the LibTcpDumpManager class.
    """
    return LibTcpDumpManager(_logger)


@st.cache_resource
def get_srt_process_manager(_logger) -> SrtProcessManager:
    """
    Retrieve a cached instance of the SrtProcessManager.

    Args:
        _logger (Logger): Logger instance to be used by SrtProcessManager.

    Returns:
        SrtProcessManager: An instance of the SrtProcessManager class.
    """
    return SrtProcessManager(_logger)


def handle_file_upload(file: runtime.uploaded_file_manager.UploadedFile) -> None:
    """
    Handle the upload of a file, validating and processing it.

    Args:
        file (UploadedFile): The uploaded file to handle.

    Returns:
        None
    """
    if not toolbox.validate_pcap_file(file):
        st.sidebar.error("Invalid capture file detected.")
        return

    logger.info("User successfully uploaded a valid capture file.")
    st.sidebar.success("Valid capture file detected.")
    save_uploaded_file(file)
    process_file(file)
    display_analysis_and_charts(file)


def save_uploaded_file(file: runtime.uploaded_file_manager.UploadedFile) -> None:
    """
    Save the uploaded file to the local filesystem.

    Args:
        file (UploadedFile): The file to save.

    Returns:
        None
    """
    with open(f"./pcaps/{file.name}", "wb") as pcap:
        pcap.write(file.getbuffer())


def process_file(file: runtime.uploaded_file_manager.UploadedFile) -> None:
    """
    Process the uploaded file by starting the tcpdump process.

    Args:
        file (UploadedFile): The file to process.

    Returns:
        None
    """
    with st.spinner(f"Processing '{file.name}'"):
        libtcpdump_manager.start_process(file)
        time.sleep(15)
    logger.info(f"{file.name} processed successfully.")


def display_analysis_and_charts(
    file: runtime.uploaded_file_manager.UploadedFile,
) -> None:
    """
    Display the analysis and charts for the processed file.

    Args:
        file (UploadedFile): The file for which to display analysis and charts.

    Returns:
        None
    """
    output = pd.read_csv(f"./pcaps/{os.path.splitext(file.name)[0]}.csv", delimiter=";")

    analysis, charts = st.tabs(["Analysis", "Charts"])
    with analysis:
        display_analysis(output)
    with charts:
        display_charts(output)


def display_analysis(output: pd.DataFrame) -> None:
    """
    Display the analysis metrics from the processed file output.

    Args:
        output (pd.DataFrame): The DataFrame containing the processed file output.

    Returns:
        None
    """
    col1, col2, col3 = st.columns(3)
    percentage_control_packets = (output["srt.iscontrol"].sum() / len(output)) * 100
    average_rtt = output["srt.rtt"].dropna().mean() / 1000

    col1.metric("Time", f"{output['_ws.col.Time'].iloc[-1]:.2f}s")
    col2.metric("Control Packets", f"{percentage_control_packets:.2f}%")
    col3.metric("Average RTT", f"{average_rtt:.2f}ms")

    st.write(libtcpdump_manager.get_output())


def display_charts(output: pd.DataFrame) -> None:
    """
    Display the charts based on the processed file output.

    Args:
        output (pd.DataFrame): The DataFrame containing the processed file output.

    Returns:
        None
    """
    draw_rtt_chart(output)
    draw_bw_chart(output)


def draw_rtt_chart(output: pd.DataFrame) -> None:
    """
    Draw the Round Trip Time (RTT) chart based on the output data.

    Args:
        output (pd.DataFrame): The DataFrame containing the processed file output.

    Returns:
        None
    """
    rtt_data = output.copy()
    rtt_data["srt.rtt_ms"] = rtt_data["srt.rtt"] / 1000
    rtt_data["_ws.col.Time"] = pd.to_numeric(rtt_data["_ws.col.Time"], errors="coerce")
    rtt_data = rtt_data.dropna(subset=["_ws.col.Time", "srt.rtt_ms"])
    toolbox.draw_plotly_line_chart(
        rtt_data,
        x="_ws.col.Time",
        y="srt.rtt_ms",
        title="Round Trip Time (RTT) over Time",
        labels={"_ws.col.Time": "Time (s)", "srt.rtt_ms": "RTT (ms)"},
    )


def draw_bw_chart(output: pd.DataFrame) -> None:
    """
    Draw the Bandwidth (BW) chart based on the output data.

    Args:
        output (pd.DataFrame): The DataFrame containing the processed file output.

    Returns:
        None
    """
    bw_data = output.copy()
    bw_data["srt.bw_mbps"] = bw_data["srt.bw"] / 1000
    bw_data["_ws.col.Time"] = pd.to_numeric(bw_data["_ws.col.Time"], errors="coerce")
    bw_data = bw_data.dropna(subset=["_ws.col.Time", "srt.bw_mbps"])
    toolbox.draw_plotly_line_chart(
        bw_data,
        x="_ws.col.Time",
        y="srt.bw_mbps",
        title="Bandwidth (BW) over Time",
        labels={"_ws.col.Time": "Time (s)", "srt.bw_mbps": "BW (Mbps)"},
    )


def display_media() -> None:
    """
    Display media content if the user opts to do so, converting files if necessary.

    Returns:
        None
    """
    display_video = st.checkbox("Display Content")

    if display_video:
        mp4_path = "./srt/received.mp4"
        ts_path = "./srt/received.ts"

        if os.path.exists(mp4_path):
            st.video(mp4_path)
        else:
            with st.spinner("Converting MPEG-TS to MP4..."):
                toolbox.convert_ts_to_mp4(input_file=ts_path, output_file=mp4_path)

            st.rerun()


def get_interfaces_with_ip() -> List[Tuple[str, str]]:
    """
    Retrieves a list of network interfaces that have an IPv4 address assigned, excluding the loopback interface.

    Returns:
        List[Tuple[str, str]]: A list of tuples where each tuple contains the interface name (str)
                               and its associated IPv4 address (str).
    """
    interfaces = netifaces.interfaces()
    interfaces_with_ips = []

    for interface in interfaces:
        if "lo" in interface:  # filter out loopback
            continue

        addresses = netifaces.ifaddresses(interface)
        if netifaces.AF_INET in addresses:  # Check if the interface has an IPv4 address
            ipv4_info = addresses[netifaces.AF_INET][0]
            ip_address = ipv4_info.get("addr")
            if ip_address:
                interfaces_with_ips.append((interface, ip_address))

    return interfaces_with_ips


def handle_timeout(
    srt_manager: Any,
    srt_timeout: int,
    selected_interface_name: str,
    counter: Any,
    connected: Any,
) -> None:
    """
    Handle the timeout loop for an SRT (Secure Reliable Transport) connection.

    This function manages the countdown for an SRT session, updating the user
    interface with the remaining time and checking the connection status. If
    a connection is established, it notifies the user. Upon timeout, it performs
    cleanup operations and resets the SRT manager's state.

    Args:
        srt_manager (Any): An object managing the SRT connection, responsible
                           for checking connection status and handling network
                           emulation.
        srt_timeout (int): The duration in seconds before the SRT session times out.
        selected_interface_name (str): The name of the network interface being used.
        counter (Any): A UI element or logger for displaying the remaining time.
        connected (Any): A UI element or logger for displaying the connection status.

    Returns:
        None
    """
    srt_connected = False
    st.button("Terminate session", type="primary")

    while srt_timeout > 0:
        counter.warning(f"SRT session expires in ```{srt_timeout}``` seconds")
        time.sleep(1)
        srt_timeout -= 1

        if srt_connected:
            continue

        if srt_manager.get_connection_status():
            srt_connected = True
            connected_host = srt_manager.extract_connected_ip_port()
            connected.info(f"Connected with ```{connected_host}```")

    # timeout completes naturally
    logger.info("SRT processes timed out...Cleaning up.")
    srt_manager.connection_established = False
    srt_manager.clear_network_emulation(selected_interface_name)
    st.rerun()


def start_srt_session(
    submitted: bool,
    srt_manager: Any,
    srt_version: str,
    srt_mode: str,
    srt_port: int,
    srt_timeout: int,
    srt_ip: str,
    selected_interface_name: str,
    netem: bool,
    delay: Optional[int] = None,
) -> None:
    """
    Start the SRT (Secure Reliable Transport) session.

    This function initiates the SRT session if the session is submitted. If
    network emulation (netem) is enabled, it adds network emulation settings
    to the specified interface with an optional delay. It then starts the SRT
    process with the specified parameters and handles the timeout loop.

    Args:
        submitted (bool): A flag indicating whether the SRT session should be started.
        srt_manager (Any): An object managing the SRT connection, responsible
                           for starting the process and handling network emulation.
        srt_version (str): The version of the SRT protocol to use.
        srt_mode (str): The mode for the SRT session (e.g., "caller", "listener").
        srt_port (int): The port number for the SRT connection.
        srt_timeout (int): The duration in seconds before the SRT session times out.
        srt_ip (str): The IP address to connect to for the SRT session.
        selected_interface_name (str): The name of the network interface being used.
        netem (bool): A flag indicating whether network emulation is enabled.
        delay (Optional[int]): An optional delay in milliseconds for network emulation.

    Returns:
        None
    """
    if not submitted:
        return

    if netem:
        logger.info("Adding networking emulation.")
        srt_manager.add_network_emulation(selected_interface_name, delay)

    srt_manager.start_process(
        srt_version,
        mode=str(srt_mode).lower(),
        port=srt_port,
        timeout=srt_timeout,
        ip=srt_ip,
    )

    counter = st.empty()
    connected = st.empty()

    handle_timeout(
        srt_manager, srt_timeout, selected_interface_name, counter, connected
    )


st.set_page_config(page_title="SRT Processor", layout="wide")
st.title("SRT Processor")
st.subheader("Interactive application for exploring SRT session statistics")
toolbox = get_toolbox()
logger = get_app_logger()
libtcpdump_manager = get_libtcpdump_manager(logger)
srt_manager = get_srt_process_manager(logger)

_HOST_INTERFACES = get_interfaces_with_ip()
_SRT_STATS = "./srt/received.ts.stats"

# initialize session state variables with defaults if they do not exist
st.session_state.setdefault("input_option", None)
st.session_state.setdefault("srt_submitted", False)

# determine the state of 'submit_disabled' based on 'srt_submitted'
st.session_state["submit_disabled"] = st.session_state.get("srt_submitted", False)

input_option = st.selectbox(
    "Select an input method",
    ["Live Transmit", "Packet Capture"],
    placeholder="Select an input method",
    label_visibility="collapsed",
    index=None,
    key="input_option",
)

# packet capture
if st.session_state.input_option == "Packet Capture":
    st.markdown(
        """
        Upload a ```.pcap(ng)``` file containing an SRT session for processing using the 
        [lib-tcpdump-processing](https://github.com/mbakholdina/lib-tcpdump-processing) 
        open source library
        """
    )
    file = st.sidebar.file_uploader(
        "Upload SRT packet capture file", type=[".pcap", ".pcapng"]
    )

    if file is not None:
        handle_file_upload(file)

# live transmit
if st.session_state.input_option == "Live Transmit":
    st.markdown(
        """
        Spawn an [srt-live-transmit](https://github.com/Haivision/srt/blob/master/docs/apps/srt-live-transmit.md) 
        process to receive a flow. This application can function as either 
        ```listener``` or ```caller``` from a session handshake perspective, 
        but will always be the receiver from a session flow perspective.
        """
    )
    with st.sidebar.container():
        srt_version = st.radio(
            "Select version", ["1.5.3", "1.5.0", "1.4.4"], horizontal=True, index=0
        )
        srt_mode = st.radio(
            "Select connection mode",
            ["Caller", "Listener"],
            horizontal=True,
            help="""
            **Listener**: The 'agent' (this application) waits to be contacted by any peer caller.
            
            **Caller**: The 'agent' (this application) sends the connection request to the peer, 
            which must be listener.
            """,
        )
        host_interfaces = [f"{intf[0]}:{intf[1]}" for intf in _HOST_INTERFACES]
        selected_interface = st.selectbox("Select host interface", host_interfaces)
        selected_interface_name = selected_interface.split(":")[0]
        selected_interface_ip = selected_interface.split(":")[1]

        if srt_mode == "Listener":
            srt_ip = selected_interface_ip
        else:  # srt_mode == "Caller"
            srt_ip = st.text_input(
                "IPv4 address of listener",
                help="IPv4 address in dotted decimal notation (i.e., 192.168.1.7).",
                placeholder="Enter a valid IPv4 address",
            )

            if srt_ip and not toolbox.validate_ipv4_address(srt_ip):
                st.error(f"**{srt_ip}** is an invalid address")
                st.session_state.submit_disabled = True

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

        if netem := st.checkbox("Add network emulation"):
            delay = st.number_input(
                "Add Delay (ms)",
                min_value=10,
                max_value=200,
                value=10,
                step=5,
                format="%d",
                help="""
                Add incremental delay, in milliseconds (ms).
                """,
            )

        submitted = st.button(
            "Submit", disabled=st.session_state.submit_disabled, key="srt_submitted"
        )

    if st.session_state.srt_submitted:
        start_srt_session(
            submitted=submitted,
            srt_manager=srt_manager,
            srt_version=srt_version,
            srt_mode=srt_mode,
            srt_port=srt_port,
            srt_timeout=srt_timeout,
            srt_ip=srt_ip,
            selected_interface_name=selected_interface_name,
            netem=netem,
            delay=delay if netem else None,
        )
    elif netem:
        srt_manager.clear_network_emulation(selected_interface_name)

    # Check if the stats file exists and is not empty
    if os.path.exists(_SRT_STATS) and os.stat(_SRT_STATS).st_size > 0:
        try:
            output = pd.read_csv(_SRT_STATS)
        except Exception as e:
            st.error(f"Error loading statistics file: {e}")
            st.stop()

        # Create the tabs
        session, transport_stream, raw_data = st.tabs(
            ["Session", "Transport Stream", "Raw Session Data"]
        )

        # session tab content
        with session:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Time", f"{output['Time'].iloc[-1] / 1000:.1f}s")
            col2.metric(
                "Average Receive Rate",
                f"{output['mbpsRecvRate'].mean():.2f}Mbps",
            )
            col3.metric("Average Round-Trip Time", f"{output['msRTT'].mean():.2f}ms")
            col4.metric(
                "Pkts Rcvd/Lost/Dropped/Retrans",
                f"{output['pktRecv'].iloc[-1]}/\
                {output['pktRcvLoss'].iloc[-1]}/\
                {output['pktRcvDrop'].iloc[-1]}/\
                {output['pktRcvRetrans'].iloc[-1]}",
            )

            # rtt
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

            # available bandwidth/receive rate
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

            # available receive buffer/receive buffer
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

            # packet stats
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

        # transport stream tab content
        with transport_stream:
            if srt_manager.check_for_valid_mpeg_ts():
                programs = srt_manager.show_mpeg_ts_programs()

                # programs dataframe
                programs_df = pd.json_normalize(programs["programs"]).drop(
                    columns=["tags.service_provider", "streams"]
                )

                st.dataframe(programs_df, hide_index=True, use_container_width=True)

                # streams dataframe
                streams_data = []
                for program in programs["programs"]:
                    streams_data.extend(program["streams"])

                streams_df = pd.json_normalize(streams_data)[
                    [
                        "index",
                        "codec_name",
                        "codec_long_name",
                        "profile",
                        "codec_type",
                        "width",
                        "height",
                        "display_aspect_ratio",
                        "field_order",
                        "start_time",
                        "duration",
                        "bit_rate",
                        "tags.language",
                    ]
                ]

                st.dataframe(streams_df, hide_index=True, use_container_width=True)

                # display content
                display_media()

            else:
                st.error("No valid MPEG-TS detected")

        # raw data tab content
        with raw_data:
            st.dataframe(output, use_container_width=True, hide_index=True)

    else:
        if not os.path.exists(_SRT_STATS):
            st.warning("Awaiting SRT session to begin...")
        else:
            logger.info("SRT session statistics file is empty.")
            st.error("SRT session statistics file is empty")

# cleanup all existing packet capture or srt output when input is cleared
if st.session_state.input_option is None:
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
