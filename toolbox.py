from timeit import default_timer as timer

import plotly.express as px
import streamlit as st
from pandas import concat


class Toolbox:
    """Docstring missing."""

    def __init__(self):
        """Docstring missing."""

    def convert_df_to_csv(self, df):
        """Docstring missing."""
        return df.to_csv(index=False).encode("utf-8")

    def draw_plotly_pie_chart(self, df, values="", names="", title=""):
        chart = px.pie(df, values=values, names=names, title=title, template="gridon")
        chart.update_traces(
            {
                "textfont_size": 15,
                "textposition": "inside",
                "textinfo": "percent+label",
                "hovertemplate": None,
                "hoverinfo": "value",
            }
        )

        return st.plotly_chart(
            chart, config={"displaylogo": False}, use_container_width=True
        )

    def draw_plotly_bar_chart(self, df, xaxis, yaxis, color="", title=""):
        """Docstring missing."""
        chart = px.bar(
            df,
            title=title,
            x=xaxis,
            y=yaxis,
            color=color,
            template="seaborn",
            text=df.percentage,
        )
        chart.update_layout(legend_title=None)
        chart.update_traces(
            {
                "textfont_size": 15,
                "textangle": 0,
                "textposition": "outside",
                "cliponaxis": False,
                "hovertemplate": None,
            }
        )

        return st.plotly_chart(
            chart, config={"displaylogo": False}, use_container_width=True
        )

    def draw_plotly_line_chart(self, df, title=""):
        chart = px.line(
            df,
            title=title,
            template="seaborn",
            markers=True,
        )
        chart.update_layout(legend_title=None)
        chart.update_traces(
            {
                "name": "count",
                "textfont_size": 15,
                "cliponaxis": False,
                "hovertemplate": None,
            }
        )

        return st.plotly_chart(
            chart, config={"displaylogo": False}, use_container_width=True
        )

    def df_counts_and_percentage(self, df, *columns):
        """Docstring missing."""
        # Normalize the percentage of each unique combination in the DataFrame based on the column
        result = df.value_counts(columns[0], normalize=True).reset_index(
            name="percentage"
        )

        # Multiply the percentages by the total count to get the actual counts
        result["count"] = result["percentage"] * df.shape[0]

        # Format to show percentage
        result["percentage"] = result["percentage"].mul(100).round(1).astype(str) + "%"

        return result

    def download_df(self, df, name):
        """Docstring missing."""
        file_name = f"nso_{name.lower()}.csv".replace(" ", "_")

        return st.download_button(
            label=f"Download {name}",
            data=self.convert_df_to_csv(df),
            type="primary",
            use_container_width=True,
            file_name=file_name,
            mime="text/csv",
        )

    def df_vertical_stack(self, frames):
        """Docstring missing."""
        return concat(frames, axis=0)

    def df_horizontal_stack(self, frames):
        """Docstring missing."""
        return concat(frames, axis=1)

    def search_df_values(self, df, condition):
        """Docstring missing."""
        for index, row in df.iterrows():
            if condition(row):
                yield row

    def add_dict_value(self, dict_obj, key, value):
        """Adds a key-value pair to the dictionary. If the key already exists
        in the dictionary, it will associate multiple values with that key
        instead of overwritting its value"""
        if key not in dict_obj:
            dict_obj[key] = value

        elif isinstance(dict_obj[key], list):
            dict_obj[key].append(value)

        else:
            dict_obj[key] = [dict_obj[key], value]

    @staticmethod
    def timer_func(func):
        """Dosctring missing."""

        def wrapper(*args, **kwargs):
            t_start = timer()
            result = func(*args, **kwargs)
            t_end = timer()
            st.write(f"**Response time:**  {(t_end - t_start):.4f} seconds")

            return result

        return wrapper
