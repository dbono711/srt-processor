import os
import time
import pandas as pd
import streamlit as st
from streamlit import runtime
from process_manager import LibTcpDumpManager


@st.cache_resource
def _get_libtcpdump_manager(_logger) -> LibTcpDumpManager:
    """
    Retrieve a cached instance of the LibTcpDumpManager.

    Args:
        _logger (Logger): Logger instance to be used by LibTcpDumpManager.

    Returns:
        LibTcpDumpManager: An instance of the LibTcpDumpManager class.
    """
    return LibTcpDumpManager(_logger)


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
    st.session_state.logger.info(f"{file.name} processed successfully.")


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
    st.session_state.toolbox.draw_plotly_line_chart(
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
    st.session_state.toolbox.draw_plotly_line_chart(
        bw_data,
        x="_ws.col.Time",
        y="srt.bw_mbps",
        title="Bandwidth (BW) over Time",
        labels={"_ws.col.Time": "Time (s)", "srt.bw_mbps": "BW (Mbps)"},
    )


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


def handle_file_upload(file: runtime.uploaded_file_manager.UploadedFile) -> None:
    """
    Handle the upload of a file, validating and processing it.

    Args:
        file (UploadedFile): The uploaded file to handle.

    Returns:
        None
    """
    if not st.session_state.toolbox.validate_pcap_file(file):
        st.sidebar.error("Invalid capture file detected.")
        return

    st.session_state.logger.info("User successfully uploaded a valid capture file.")
    st.sidebar.success("Valid capture file detected.")
    save_uploaded_file(file)
    process_file(file)
    display_analysis_and_charts(file)


if "toolbox" not in st.session_state:
    st.switch_page("Home.py")

st.set_page_config(page_title="SRT Processor", layout="wide")
st.title("SRT Packet Capture Analysis")
st.markdown(
    """
    Upload a ```.pcap(ng)``` file containing an SRT session for processing using the 
    [lib-tcpdump-processing](https://github.com/mbakholdina/lib-tcpdump-processing) 
    open source library

    _**NOTE:** The last capture's statistics will persist until a new 
    upload is initiated, or the file removed._
    """
)

libtcpdump_manager = _get_libtcpdump_manager(st.session_state.logger)

file = st.sidebar.file_uploader(
    "Upload SRT packet capture file", type=[".pcap", ".pcapng"]
)

if file is not None:
    handle_file_upload(file)
