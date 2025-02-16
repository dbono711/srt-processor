import os
import time
from typing import Any, List, Optional, Tuple

import netifaces
import pandas as pd
import plotly_express as px
import streamlit as st

from process_manager import SrtProcessManager


@st.cache_resource
def _get_srt_process_manager(_logger) -> SrtProcessManager:
    """
    Retrieve a cached instance of the SrtProcessManager.

    Args:
        _logger (Logger): Logger instance to be used by SrtProcessManager.

    Returns:
        SrtProcessManager: An instance of the SrtProcessManager class.
    """
    return SrtProcessManager(_logger)


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
    st.session_state.logger.info("SRT processes timed out...Cleaning up.")
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
        st.session_state.logger.info("Adding networking emulation.")
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


if "toolbox" not in st.session_state:
    st.switch_page("Home.py")

st.set_page_config(page_title="SRT Processor", layout="wide")
st.title("SRT Live Transmit Analysis")
st.markdown(
    """
    Spawn an [srt-live-transmit](https://github.com/Haivision/srt/blob/master/docs/apps/srt-live-transmit.md) 
    process. This application can function as either ```listener``` or ```caller``` 
    from a session handshake perspective, but will always be the receiver from a 
    session flow perspective.

    _**NOTE:** The last session's statistics will be displayed until a new 
    one is initiated. In other words, every new session overwrites the last._
    """
)

_HOST_INTERFACES = get_interfaces_with_ip()
_SRT_STATS = "./srt/received.ts.stats"

srt_manager = _get_srt_process_manager(st.session_state.logger)

# determine the state of 'submit_disabled' based on 'srt_submitted'
st.session_state["submit_disabled"] = st.session_state.get("srt_submitted", False)

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
            "*IPv4 address of listener",
            help="IPv4 address in dotted decimal notation (i.e., 192.168.1.7).",
            placeholder="Enter a valid IPv4 address",
        )

        if not srt_ip:
            st.session_state.submit_disabled = True
        elif srt_ip and not st.session_state.toolbox.validate_ipv4_address(srt_ip):
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
    # clear out any pre-existing network emulation settings
    srt_manager.clear_network_emulation(selected_interface_name)

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

if not os.path.exists(_SRT_STATS):
    st.warning("Awaiting SRT session to begin...")
elif os.stat(_SRT_STATS).st_size == 0:
    st.session_state.logger.info("SRT session statistics file is empty.")
    st.error("SRT session statistics file is empty.")
else:
    try:
        output = pd.read_csv(_SRT_STATS)

        # calculate the jitter by taking the absolute differences between consecutive msRTT values
        output["jitter"] = output["msRTT"].diff().abs()

    except Exception as e:
        st.error(f"Error loading statistics file: {e}")
        st.stop()

    # Create the tabs
    session, transport_stream, raw_data = st.tabs(
        ["Session", "Transport Stream", "Raw Session Data"]
    )

    # session tab content
    with session:
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Session Time", f"{output['Time'].iloc[-1] / 1000:.1f}s")
        col2.metric(
            "Average Receive Rate",
            f"{output['mbpsRecvRate'].mean():.2f}Mbps",
        )
        col3.metric("Average Round-Trip Time", f"{output['msRTT'].mean():.2f}ms")
        col4.metric("Average Jitter", f"{output['jitter'].mean():.2f}ms")
        col5.metric(
            "Pkts Rcvd/Lost/Dropped/Retrans",
            f"{output['pktRecv'].iloc[-1]}/\
            {output['pktRcvLoss'].iloc[-1]}/\
            {output['pktRcvDrop'].iloc[-1]}/\
            {output['pktRcvRetrans'].iloc[-1]}",
        )

        # round-trip time/jitter
        with st.expander("Round-Trip Time (RTT) & Jitter"):
            st.write(
                """
                ```Round-Trip Time``` and ```Jitter``` are key metrics for performance in an SRT 
                session, revealing any periods of high delay or instability that could affect the 
                quality of service. These metrics provide critical insights into network performance, 
                but they represent different aspects of the connection.

                _**Direct Correlation:**_ In many cases, an increase in ```Round-Trip Time``` might 
                lead to an increase in ```Jitter```, as network congestion or instability can affect 
                both. However, this is not always the case. It is possible to have a high 
                ```Round-Trip Time``` with relatively low ```Jitter```, meaning that the delay is 
                consistent. Similarly, low ```Round-Trip Time``` with high ```Jitter``` indicates 
                rapid fluctuations in network performance.

                _**Importance in Performance:**_ While ```Round-Trip Time``` is important for determining 
                the overall speed of a connection, ```Jitter``` is crucial for assessing the stability of 
                that connection. Real-time applications can often tolerate higher ```Round-Trip Time``` 
                if the ```Jitter``` remains low, ensuring smooth packet delivery.
                """
            )

            rtt_jitter_data = output.copy()
            rtt_jitter_data = rtt_jitter_data.dropna(
                subset=["Timepoint", "msRTT", "jitter"]
            )

            rtt_jitter_data = rtt_jitter_data.melt(
                id_vars=["Timepoint"],
                value_vars=["msRTT", "jitter"],
                var_name="Metric",
                value_name="Value",
            )

            rtt_jitter_data["Metric"] = rtt_jitter_data["Metric"].map(
                {
                    "msRTT": "Round-Trip Time (RTT)",
                    "jitter": "Jitter",
                }
            )

            st.session_state.toolbox.draw_plotly_line_chart(
                rtt_jitter_data,
                x="Timepoint",
                y="Value",
                title="Round-Trip Time (RTT) and Jitter over Time",
                color="Metric",
                labels={
                    "Timepoint": "Time (s)",
                    "Value": "Milliseconds (ms)",
                    "Metric": "",
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

            st.session_state.toolbox.draw_plotly_line_chart(
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
                    tickfont=dict(color="#1f77b4"),
                ),
                yaxis2=dict(
                    title="Available Receive Buffer (Bytes)",
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
        with st.expander("Packets Received, Lost, Dropped, Retransmitted"):
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

            st.session_state.toolbox.draw_plotly_line_chart(
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

            # base columns
            base_columns = [
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

            # extract only the columns that exist in the data
            present_columns = [
                col
                for col in base_columns
                if col in pd.json_normalize(streams_data, errors="ignore").columns
            ]

            # normalize the JSON and select only existing columns
            streams_df = pd.json_normalize(streams_data, errors="ignore")[
                present_columns
            ]

            st.dataframe(streams_df, hide_index=True, use_container_width=True)

            # download content
            with open("srt/received.ts", "rb") as file:
                st.download_button(
                    label="Download MPEG-TS",
                    data=file,
                    file_name="received.ts",
                )

        else:
            st.error("No valid MPEG-TS detected")

    # raw data tab content
    with raw_data:
        st.dataframe(output, use_container_width=True, hide_index=True)
