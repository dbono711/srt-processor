import socket
import pandas as pd
import plotly.express as px
import streamlit as st

from ipaddress import ip_address
from typing import Dict


class Toolbox:
    """A utility class for performing various tasks such as plotting charts
    and handling network operations."""

    def __init__(self):
        """Initialize the Toolbox class."""
        pass

    def draw_plotly_line_chart(
        self,
        df: pd.DataFrame,
        x: str = "",
        y: str = "",
        title: str = "",
        color: str = None,
        labels: Dict[str, str] = None,
    ) -> None:
        """Draw a Plotly line chart and display it using Streamlit.

        Args:
            df (pd.DataFrame): The DataFrame containing the data to be plotted.
            x (str, optional): The column name for the x-axis.
            y (str, optional): The column name for the y-axis.
            title (str, optional): The title of the chart.
            color (str, optional): What column should be used to color the lines.
            labels (dict, optional): A dictionary for renaming labels.
        """
        labels = labels or {}

        chart = px.line(
            df,
            x=x,
            y=y,
            title=title,
            template="seaborn",
            color=color,
            labels=labels,
        )

        chart.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(chart, config={"displaylogo": False}, use_container_width=True)

    def get_primary_ip_address(self) -> str:
        """Return the primary IP address of the host this script is running on

        Returns:
            str: Primary IP address of host
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            primary_ip = s.getsockname()[0]
            s.close()

            return primary_ip

        except Exception as e:
            return st.error(f"An error occurred: {e}")

    def validate_ipv4_address(self, ipv4_address: str) -> bool:
        """Validate an address is a valid IPv4 address

        Args:
            ipv4_address (str): IPv4 address in dotted decimal notation

        Returns:
            bool: True if the address is a valid IPv4 address, else False
        """
        try:
            ip_address(ipv4_address)
            return True
        except ValueError:
            return False
