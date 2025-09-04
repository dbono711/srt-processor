# Use the official slim Python image as the base image
FROM python:3.11-slim

# Set the PATH environment variable to include the root user's local binary directory
ENV PATH="/root/.local/bin:${PATH}"

# Upgrade pip to the latest version
RUN pip install --upgrade pip

# Update the package list and install necessary packages
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    libssl-dev \
    cmake \
    build-essential \
    iproute2 \
    sudo \
    && apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create non-root user for security but allow sudo for tc command
RUN groupadd -r srtuser && useradd -r -g srtuser -m srtuser
RUN echo "srtuser ALL=(root) NOPASSWD: /usr/sbin/tc" >> /etc/sudoers

# Clone the SRT repository
RUN git clone https://github.com/Haivision/srt.git /opt/srt

# Create the local bin directory for binaries
RUN mkdir -p /root/.local/bin

# Define the SRT versions to build
ARG SRT_VERSIONS="v1.4.4 v1.5.0 v1.5.3"

# Loop through each version, checkout, build in a version-specific 'build' directory, and copy binary
RUN for version in ${SRT_VERSIONS}; do \
    cd /opt/srt && \
    git checkout $version && \
    mkdir -p build_$version && \
    cd build_$version && \
    cmake .. && \
    make && \
    cp /opt/srt/build_$version/srt-live-transmit /usr/local/bin/srt-live-transmit-$version && \
    chmod +x /usr/local/bin/srt-live-transmit-$version; \
    done

# Change the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container's /app directory
COPY . .

# Set up permissions for srtuser
RUN chown -R srtuser:srtuser /app

# Switch to srtuser for installing Python dependencies
USER srtuser

# Install the Python dependencies in srtuser's local directory
RUN pip install --user -r docker_requirements.txt

# Set PATH for non-root user to access binaries
ENV PATH="/home/srtuser/.local/bin:/usr/local/bin:${PATH}"

# Expose TCP port 8501 for the Streamlit application
EXPOSE 8501/tcp

# Expose UDP ports 9000-9100 for the SRT sessions
EXPOSE 9000-9100/udp

# Define the command to run the Streamlit application
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
