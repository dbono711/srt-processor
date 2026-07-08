import netifaces
import os
import time

import pandas as pd
import plotly.express as px
import streamlit as st

from loggerfactory import LoggerFactory
from openai import OpenAI
from process_manager import SrtProcessManager
from toolbox import Toolbox
from typing import List, Optional, Tuple


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


def _get_interfaces_with_ip() -> List[Tuple[str, str]]:
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


@st.fragment(run_every="1s")
def _srt_countdown_fragment(srt_manager: SrtProcessManager) -> None:
    """
    Display the countdown for an active SRT session and clean up on expiry.

    Reruns on its own 1s cadence (via st.fragment) instead of blocking the
    whole script with a sleep loop, so the rest of the app stays interactive
    while a session is counting down. Session state lives on srt_manager
    (not st.session_state) since it's a process-global singleton shared by
    every browser tab, and the countdown/connection status should reflect
    whichever session is actually running.

    Args:
        srt_manager (SrtProcessManager): An object managing the SRT connection, responsible
                           for checking connection status and handling network
                           emulation.

    Returns:
        None
    """
    remaining = srt_manager.get_session_remaining_seconds()
    if remaining is None:
        return

    if remaining <= 0:
        logger.info("SRT processes timed out...Cleaning up.")
        srt_manager.connection_established = False
        srt_manager.session_end_ts = None
        st.rerun()
        return

    st.button("Terminate session", type="primary")
    st.warning(f"SRT session expires in ```{int(remaining)}``` seconds")

    if srt_manager.get_connection_status() and srt_manager.connected_host:
        st.info(f"Connected with ```{srt_manager.connected_host}```")


def _start_srt_session(
    srt_manager: SrtProcessManager,
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
    process with the specified parameters.

    Args:
        srt_manager (SrtProcessManager): An object managing the SRT connection, responsible
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

    # clear out any pre-existing network emulation settings
    logger.info(f"Clearing any pre-existing network emulation for interface {selected_interface_name}")
    srt_manager.clear_network_emulation(selected_interface_name)

    if netem:
        logger.info(f"Adding networking emulation for interface {selected_interface_name} with {delay}ms delay")
        srt_manager.add_network_emulation(selected_interface_name, delay)

    st.session_state["llm_summary_text"] = None

    srt_manager.start_process(
        srt_version,
        mode=str(srt_mode).lower(),
        port=srt_port,
        timeout=srt_timeout,
        ip=srt_ip,
    )



@st.cache_data(show_spinner=False, max_entries=5)
def _read_data(stats_file: str, mtime: float) -> pd.DataFrame | None:
    """Load and process SRT statistics from a CSV file.

    Cached on (stats_file, mtime) so unrelated reruns (e.g. sidebar widget
    changes) don't reprocess the whole, potentially large, growing CSV -
    only a rerun after the file has actually changed does.

    Args:
        stats_file (str): Path to the statistics file
        mtime (float): Last-modified time of stats_file, used as a cache-busting key

    Returns:
        pd.DataFrame or None: Processed statistics or None if error
    """
    try:
        # Load the CSV file and exclude the 'Time.1' column
        data = pd.read_csv(stats_file, usecols=lambda x: x != 'Time.1')

        # Calculate the jitter by taking the absolute differences between consecutive msRTT values
        data["jitter"] = data["msRTT"].diff().abs()

        return data
    except Exception as e:
        st.error(f"Error loading statistics file: {e}")
        logger.error(f"Failed to load statistics: {e}")
        return None


def _display_session_metrics(data: pd.DataFrame) -> None:
    """Display key session metrics at the top of the page.

    Args:
        data (pd.DataFrame): The processed statistics data

    Returns:
        None
    """
    # Create rows of columns
    row1_col1, row1_col2, row1_col3, row1_col4, row1_col5 = st.columns(5)

    # Display metrics
    row1_col1.metric(
        "Session Time",
        f"{data['Time'].iloc[-1] / 1000:.1f}s",
        help="Session time in seconds"
    )
    row1_col2.metric(
        "Average Receive Rate",
        f"{data['mbpsRecvRate'].mean():.2f}Mbps",
        help="Average receive rate in Mbps"
    )
    row1_col3.metric(
        "Average Round-Trip Time",
        f"{data['msRTT'].mean():.2f}ms",
        help="Average round-trip time in ms"
    )
    row1_col4.metric(
        "Average Jitter",
        f"{data['jitter'].mean():.2f}ms",
        help="Average jitter in ms"
    )
    row1_col5.metric(
        "Packets",
        f"{data['pktRecv'].iloc[-1]}/{data['pktRcvLoss'].iloc[-1]}/{data['pktRcvDrop'].iloc[-1]}/{data['pktRcvRetrans'].iloc[-1]}",
        help="Received/Lost/Dropped/Retransmitted"
    )


def _display_rtt_jitter_metrics(data: pd.DataFrame) -> None:
    """Display RTT and jitter metrics with explanations and charts.

    Args:
        data (pd.DataFrame): The processed statistics data
    """
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

        # Prepare data for visualization - select only needed columns first
        # This reduces memory usage and improves processing speed
        rtt_jitter_data = data[["Timepoint", "msRTT", "jitter"]].copy()

        # Remove rows with missing values in any of the three columns
        # This ensures clean data for plotting without gaps or errors
        rtt_jitter_data = rtt_jitter_data.dropna()

        # Transform data from wide to long format for multi-line Plotly visualization
        # This creates a single 'Value' column with separate rows for each metric
        rtt_jitter_data = rtt_jitter_data.melt(
            id_vars=["Timepoint"],
            value_vars=["msRTT", "jitter"],
            var_name="Metric",
            value_name="Value",
        )

        # Map SRT technical column names to user-friendly display labels
        # This improves chart readability and legend clarity
        rtt_jitter_data["Metric"] = rtt_jitter_data["Metric"].map(
            {
                "msRTT": "Round-Trip Time (RTT)",
                "jitter": "Jitter",
            }
        )

        # Draw the chart
        toolbox.draw_plotly_line_chart(
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


def _display_bandwidth_metrics(data: pd.DataFrame) -> None:
    """Display bandwidth and receive rate metrics with explanations and charts.

    Args:
        data (pd.DataFrame): The processed statistics data
    """
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

        # Prepare data for visualization - select only needed columns first
        # This reduces memory usage and improves processing speed
        bandwidth_data = data[["Timepoint", "mbpsBandwidth", "mbpsRecvRate"]].copy()

        # Remove rows with missing values in any of the three columns
        # This ensures clean data for plotting without gaps or errors
        bandwidth_data = bandwidth_data.dropna()


        # Convert bandwidth from Kbps to Mbps for consistent units with receive rate
        # mbpsBandwidth appears to be in Kbps despite the name, so divide by 1000
        bandwidth_data["mbpsBandwidth"] = bandwidth_data["mbpsBandwidth"] / 1000

        # Transform data from wide to long format for Plotly visualization
        # This creates a single 'Value' column with separate rows for each metric
        bandwidth_data = bandwidth_data.melt(
            id_vars=["Timepoint"],
            value_vars=["mbpsBandwidth", "mbpsRecvRate"],
            var_name="Metric",
            value_name="Value",
        )

        # Map technical column names to user-friendly display labels
        # This improves chart readability and legend clarity
        bandwidth_data["Metric"] = bandwidth_data["Metric"].map(
            {
                "mbpsBandwidth": "Available Bandwidth",
                "mbpsRecvRate": "Receive Rate",
            }
        )

        # Draw the chart
        toolbox.draw_plotly_line_chart(
            bandwidth_data,
            x="Timepoint",
            y="Value",
            title="Receive Rate and Available Bandwidth over Time",
            color="Metric",
            labels={"Timepoint": "Time (s)", "Value": "Mbps", "Metric": ""},
        )


def _display_buffer_metrics(data: pd.DataFrame) -> None:
    """Display buffer metrics with explanations and charts.

    Args:
        data (pd.DataFrame): The processed statistics data
    """
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

        # Prepare data for visualization - select only needed columns first
        # This reduces memory usage and improves processing speed
        buffer_data = data[["Timepoint", "byteAvailRcvBuf", "msRcvBuf"]].copy()

        # Remove rows with missing values in any of the three columns
        # This ensures clean data for plotting without gaps or errors
        buffer_data = buffer_data.dropna()

        # Create the chart with dual y-axes
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

        # Display the chart
        st.plotly_chart(
            buffer_chart,
            config={"displaylogo": False},
            width="stretch",
        )


def _display_packet_metrics(data: pd.DataFrame) -> None:
    """Display packet statistics with explanations and charts.

    Args:
        data (pd.DataFrame): The processed statistics data
    """
    with st.expander("Packet Statistics"):
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

        # Prepare data for visualization - select only needed columns first
        # This reduces memory usage and improves processing speed
        packet_data = data[["Timepoint", "pktRecv", "pktRcvLoss", "pktRcvDrop", "pktRcvRetrans"]].copy()

        # Remove rows with missing values in any of the three columns
        # This ensures clean data for plotting without gaps or errors
        packet_data = packet_data.dropna()

        # Transform data from wide to long format for multi-line Plotly visualization
        # This allows plotting all packet metrics on the same chart with separate lines
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

        # Map SRT technical column names to user-friendly display labels
        # This improves chart readability and provides clear metric descriptions
        packet_data["Metric"] = packet_data["Metric"].map(
            {
                "pktRecv": "Packets Received",
                "pktRcvLoss": "Received Packets Lost",
                "pktRcvDrop": "Received Packets Dropped",
                "pktRcvRetrans": "Received Packets Retransmitted",
            }
        )

        # Draw the chart
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


@st.fragment(run_every="5s")
def _display_frame_preview(srt_manager: SrtProcessManager) -> None:
    """Display a live preview frame captured from the in-progress MPEG-TS capture.

    Reruns on its own 5s cadence (via st.fragment) independent of the rest of
    the app, so the preview doesn't need any other widget interaction to
    refresh, and other widgets aren't slowed down by it either.

    Args:
        srt_manager (SrtProcessManager): The SRT process manager instance
    """
    if not srt_manager.check_if_running():
        st.info("Frame preview will appear once an SRT session is active.")
        return

    if not srt_manager.check_for_valid_mpeg_ts():
        st.info("Waiting for a valid MPEG-TS stream to preview...")
        return

    frame_path = srt_manager.capture_preview_frame()
    if frame_path is None:
        st.info("Unable to capture a preview frame yet (stream may be too short).")
        return

    st.image(frame_path, caption=f"Live preview - updated {time.strftime('%H:%M:%S')}", width="stretch")


def _display_transport_stream_data(srt_manager: SrtProcessManager) -> None:
    """Display transport stream data if available.

    Args:
        srt_manager (SrtProcessManager): The SRT process manager instance
    """
    if srt_manager.check_for_valid_mpeg_ts():
        programs = srt_manager.show_mpeg_ts_programs()

        # Extract and display programs data
        programs_data = programs["programs"]
        programs_df = pd.DataFrame([
            {
                "program_id": p["program_id"],
                "program_num": p["program_num"],
                "nb_streams": p["nb_streams"],
                "pmt_pid": p["pmt_pid"],
                "pcr_pid": p["pcr_pid"],
                "service_name": p["tags"]["service_name"]
            }
            for p in programs_data
        ])
        st.dataframe(programs_df, hide_index=True, width="stretch")

        # Extract and display streams data efficiently
        streams_data = []
        for program in programs_data:
            for stream in program["streams"]:
                # Extract only the fields we need
                stream_info = {
                    "index": stream.get("index"),
                    "codec_name": stream.get("codec_name"),
                    "codec_long_name": stream.get("codec_long_name"),
                    "profile": stream.get("profile"),
                    "codec_type": stream.get("codec_type"),
                    "width": stream.get("width"),
                    "height": stream.get("height"),
                    "display_aspect_ratio": stream.get("display_aspect_ratio"),
                    "field_order": stream.get("field_order"),
                    "start_time": stream.get("start_time"),
                    "duration": stream.get("duration"),
                    "bit_rate": stream.get("bit_rate"),
                    "language": stream.get("tags", {}).get("language")
                }
                streams_data.append(stream_info)

        streams_df = pd.DataFrame(streams_data)
        st.dataframe(streams_df, hide_index=True, width="stretch")

        # Add download button
        with open("srt/received.ts", "rb") as file:
            st.download_button(
                label="Download MPEG-TS",
                data=file,
                file_name="received.ts",
            )
    else:
        st.warning("Awaiting complete MPEG-TS data...")


def _display_raw_data(data: pd.DataFrame) -> None:
    """Display raw session data in a dataframe.

    Args:
        data (pd.DataFrame): The processed statistics data
    """
    st.dataframe(data, width="stretch", hide_index=True)


@st.cache_data(show_spinner="Analyzing SRT session data with AI...", max_entries=10)
def _generate_llm_summary(csv_data: str, api_key: str) -> str:
    """Call the OpenAI Responses API to analyze one session's CSV data.

    csv_data is part of the cache key (along with api_key), so a different
    session's data produces a fresh call instead of reusing a stale result
    from an earlier session. Returns text rather than rendering directly, so
    the caller controls when/whether it's displayed.

    Args:
        csv_data (str): Raw SRT session statistics CSV content to analyze.
        api_key (str): OpenAI API key.

    Returns:
        str: The LLM-generated analysis, as markdown text.
    """
    instructions = """
        # Role and Objective
        You are an SRT (Secure Reliable Transport) streaming analysis expert. Your primary goal is to help network engineers, broadcasters, and streaming professionals analyze SRT session statistics, identify performance issues, and optimize streaming configurations.

        # Application Context - IMPORTANT
        This application is ALWAYS the SRT receiver/destination for video streaming:
        - **SRT Handshake Role**: Can be either "SRT Listener" or "SRT Caller"
        - **SRT Flow Direction**: ALWAYS the receiver - never sends video content
        - **Data Analysis Focus**: All statistics are from the receiver's perspective
        - **Stream Direction**: Video flows FROM remote source TO this application

        # Available Data Context
        You have access to SRT receiver-side statistics including:
        - Round-Trip Time (RTT) and jitter measurements
        - Bandwidth utilization and receive rates
        - Buffer metrics (available receive buffer, receive buffer time)
        - Packet statistics (received, lost, dropped, retransmitted)
        - Session duration and connection details

        # Instructions
        ## Analysis Guidelines
        - Focus on receiver-side SRT performance metrics and their implications
        - Identify patterns in network behavior that affect streaming quality at the destination
        - Correlate different metrics to diagnose root causes of reception issues
        - Provide actionable recommendations for SRT receiver configuration optimization

        ## Response Guidelines
        - Provide technical insights relevant to live streaming reception and SRT protocols
        - Explain how network conditions impact streaming quality and user experience at the receiver
        - Suggest specific SRT receiver parameter adjustments when appropriate
        - Use streaming industry terminology and best practices for destination/receiver optimization

        # Key Analysis Areas
        1. **Network Stability**: Analyze RTT and jitter patterns for connection quality
        2. **Reception Efficiency**: Compare available bandwidth vs actual receive rates
        3. **Buffer Management**: Evaluate receiver buffer utilization and potential underruns/overruns
        4. **Packet Loss Recovery**: Assess retransmission effectiveness and loss patterns from receiver perspective
        5. **Session Health**: Overall connection stability and reception performance trends

        # Output Format
        - **Performance Summary**: Brief overview of reception session health
        - **Key Findings**: Bullet points highlighting important observations from receiver perspective
        - **Recommendations**: Specific actions to improve streaming reception performance
        - **Technical Details**: Detailed analysis with supporting receiver-side data

        # Examples
        ## Example 1: High Jitter Analysis
        "The receiver shows significant jitter spikes (>50ms) correlating with packet loss events. This suggests network congestion affecting reception quality. Recommend increasing SRT receiver latency buffer (SRTO_RCVLATENCY) and configuring adaptive reception parameters to handle network instability."

        ## Example 2: Buffer Optimization
        "Available receive buffer consistently near zero indicates potential underruns at the receiver. Consider increasing SRTO_RCVBUF size or requesting sender to reduce encoding bitrate to match receiver's network capacity."

        Focus on providing actionable insights that help optimize SRT streaming reception performance and troubleshoot network-related issues affecting live video delivery to this destination.

        Do not ask the user for additional context or input.
    """

    client = OpenAI(api_key=api_key)

    # Load SRT statistics documentation for context
    statistics_doc = ""
    try:
        with open("statistics.md", "r") as f:
            statistics_doc = f.read()
    except FileNotFoundError:
        logger.warning("statistics.md not found - analysis will proceed without detailed metric definitions")

    # Prepare input with documentation context
    analysis_input = \
        f"""# SRT Statistics Documentation Context
        {statistics_doc}

        # SRT Session CSV Data to Analyze
        {csv_data}
    """

    response = client.responses.create(
        model="gpt-5-mini",
        instructions=instructions,
        input=f"Using the SRT statistics documentation provided as context, analyze this SRT session CSV data and provide detailed insights:\n\n{analysis_input}"
    )

    return response.output_text


def _display_llm_summary() -> None:
    """Button-gated trigger for the LLM summary, persisted across reruns.

    Replaces the previous automatic-on-every-rerun behavior: the OpenAI call
    now only happens when the user explicitly clicks "Generate Summary". The
    result is stored in st.session_state so it keeps displaying across
    unrelated reruns/tab switches without needing to re-click.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.warning("🔑 LLM Analysis Unavailable")
        st.info("To enable AI-powered analysis of your SRT session data, provide an OpenAI API key as an environment variable when running the container:")

        return

    if st.button("Generate Summary", key="generate_llm_summary"):
        try:
            with open(_SRT_STATS, "r") as f:
                csv_data = f.read()

            st.session_state["llm_summary_text"] = _generate_llm_summary(csv_data, api_key)
        except Exception as e:
            st.session_state["llm_summary_text"] = None
            st.error(f"LLM Analysis failed: {str(e)}")
            st.info("Please verify your OpenAI API key is valid and has sufficient credits.")
            return

    if st.session_state.get("llm_summary_text"):
        st.markdown(st.session_state["llm_summary_text"])


@st.fragment(run_every="3s")
def _display_session_content(srt_manager: SrtProcessManager) -> None:
    """Render the main content area: awaiting-data placeholder, error, or the tabs.

    Reruns on its own 3s cadence (via st.fragment) so this picks up a
    session's stats file appearing/updating on its own, instead of staying
    on "Awaiting SRT session to begin..." until some unrelated widget
    interaction happens to trigger a full script rerun.

    Args:
        srt_manager (SrtProcessManager): The SRT process manager instance
    """
    if not os.path.exists(_SRT_STATS):
        st.warning("Awaiting SRT session to begin...")
        return

    if os.stat(_SRT_STATS).st_size == 0:
        logger.info("SRT session statistics file is empty.")
        st.error("SRT session statistics file is present, but is empty.")
        return

    logger.info("Displaying SRT session data...")

    with st.spinner("Analyzing SRT session data..."):
        # load and process statistics
        data = _read_data(_SRT_STATS, os.stat(_SRT_STATS).st_mtime)
        if data is None:
            st.stop()

        _display_session_metrics(data)

        # create tabs
        summary, charts, transport_stream, raw_data = st.tabs(
            ["Summary", "Charts", "Transport Stream", "Raw Session Data"]
        )

        # summary tab content
        with summary:
            _display_llm_summary()

        # session tab content
        with charts:
            # display detailed metrics in expandable sections
            _display_rtt_jitter_metrics(data)
            _display_bandwidth_metrics(data)
            _display_buffer_metrics(data)
            _display_packet_metrics(data)

        # transport stream tab content
        with transport_stream:
            _display_transport_stream_data(srt_manager)

        # raw data tab content
        with raw_data:
            _display_raw_data(data)


# Main content start
st.set_page_config(page_title="SRT Processor", layout="wide", page_icon="")
st.title("SRT Processor")
st.markdown(
    """
    Interactive application for analyzing Secure Reliable Transport (SRT) flows using
    [srt-live-transmit](https://github.com/Haivision/srt/blob/master/docs/apps/srt-live-transmit.md).
    The application can function as either ```listener``` or ```caller```
    from a session handshake perspective, but will always be the receiver from a
    session flow perspective. The analysis is based on statistics generated by the
    srt-live-transmit process, which are logged every 100 packets. The
    most recent session will be displayed until a new one is initiated.
    """
)

_SRT_STATS = "./srt/received.ts.stats"

toolbox = Toolbox()
logger = LoggerFactory.get_logger("app", log_level="WARNING")
srt_manager = _get_srt_process_manager(logger)

# determine the state of 'submit_disabled' based on whether a session is actively running,
# rather than the transient 'srt_submitted' click flag, since starting a session no longer
# blocks the script until it completes
st.session_state["submit_disabled"] = srt_manager.check_if_running()

# initialize sidebar
with st.sidebar.container():

    # SRT version selection
    srt_version = st.radio(
        "Select version", ["1.5.3", "1.5.0", "1.4.4"], horizontal=True, index=0
    )

    # SRT mode selection
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
    host_interfaces = [f"{intf[0]}:{intf[1]}" for intf in _get_interfaces_with_ip()]
    selected_interface = st.selectbox("Select host interface", host_interfaces)
    selected_interface_name = selected_interface.split(":")[0]
    selected_interface_ip = selected_interface.split(":")[1]

    # srt_mode == "Listener"
    if srt_mode == "Listener":
        srt_ip = selected_interface_ip

    # srt_mode == "Caller"
    else:
        # get listener IP address with integrated validation
        listener_ip = st.text_input(
            "*IPv4 address of listener",
            help="IPv4 address in dotted decimal notation (i.e., 192.168.1.7).",
            placeholder="Enter a valid IPv4 address",
            key="listener_ip_input"
        )

        # validate IP address and update UI accordingly
        if not listener_ip:
            st.warning("Please enter the listener's IP address")
            st.session_state.submit_disabled = True
            srt_ip = ""
        elif not toolbox.validate_ipv4_address(listener_ip):
            st.error(f"**{listener_ip}** is not a valid IPv4 address. Please use format: xxx.xxx.xxx.xxx")
            st.session_state.submit_disabled = True
            srt_ip = ""
        else:
            srt_ip = listener_ip

    # SRT port selection
    srt_port = st.number_input(
        "Select port",
        min_value=9000,
        max_value=9100,
        value=9000,
        step=1,
        format="%d",
        help="Port for the SRT session (9000-9100).",
    )

    # SRT timeout selection
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

    # network emulation selection
    if netem := st.checkbox(
        "Add network emulation",
        help="""
        Network emulation using Linux Traffic Control (tc) artificially introduces
        delay to simulate real-world network conditions. When enabled, tc modifies
        the container's network interface to add configurable millisecond delays to
        incoming & outgoing packets, allowing you to test how SRT performs under
        various network conditions such as satellite links, congested networks, or
        unstable connections. This helps evaluate SRT's adaptive bitrate, retransmission,
        and buffering mechanisms in a controlled environment.
        """):
        delay = st.number_input(
            "Add Delay (ms)",
            min_value=1,
            max_value=200,
            value=10,
            step=1,
            format="%d",
            help="""
            Add incremental delay, in milliseconds (ms) (1-200).
            """,
        )

    # submit button
    submitted = st.button(
        "Submit", disabled=st.session_state.submit_disabled, key="srt_submitted"
    )

    # live preview lives here (rather than the Transport Stream tab) so it's visible
    # even before any stats data exists yet - e.g. on the very first session, before
    # the main content area has anything to show
    _display_frame_preview(srt_manager)

# handle submitted session
if st.session_state.srt_submitted:
    _start_srt_session(
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

# render the countdown for an active session on every rerun, not just the one where
# the session was started, so the fragment stays alive across unrelated reruns
if srt_manager.session_end_ts is not None:
    _srt_countdown_fragment(srt_manager)

# display tabs and their content
_display_session_content(srt_manager)
