# Use the official slim Python image as the base image
FROM python:3.11-slim

# Set the PATH environment variable to include the root user's local binary directory
ENV PATH="/root/.local/bin:${PATH}"

# Upgrade pip to the latest version
RUN pip install --upgrade pip

# Update the package list and install necessary packages
RUN apt-get update && apt-get install -y \
    git \
    tshark \
    ffmpeg \
    libssl-dev \
    cmake \
    build-essential \
    iproute2 \
    && rm -rf /var/lib/apt/lists/* # Clean up the package lists to reduce image size

# Clone the lib-tcpdump-processing repository
RUN git clone https://github.com/mbakholdina/lib-tcpdump-processing.git /opt/libtcpdump

# Change the working directory to the cloned repository
WORKDIR /opt/libtcpdump

# Install the Python package in the root user's local directory
RUN pip install --user .

# Clone the SRT repository
RUN git clone https://github.com/Haivision/srt.git /opt/srt

# Define the SRT versions to build
ARG SRT_VERSIONS="v1.4.4 v1.5.0 v1.5.3"

# Loop through each version, checkout, build in a version-specific 'build' directory, and create symbolic link
RUN for version in ${SRT_VERSIONS}; do \
    cd /opt/srt && \
    git checkout $version && \
    mkdir -p build_$version && \
    cd build_$version && \
    cmake .. && \
    make && \
    ln -s /opt/srt/build_$version/srt-live-transmit /root/.local/bin/srt-live-transmit-$version; \
    done

# Change the working directory to /app
WORKDIR /app

# Copy the Docker development requirements into the container's /app directory
COPY docker_dev_requirements.txt .

# Install the Python dependencies listed in docker_requirements.txt in the root user's local directory
RUN pip install --user -r docker_dev_requirements.txt

# Expose TCP port 8501 for the Streamlit application
EXPOSE 8501/tcp

# Expose UDP ports 9000-9100 for the SRT sessions
EXPOSE 9000-9100/udp
