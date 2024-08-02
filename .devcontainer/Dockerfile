# Use the official slim Python image as the base image
FROM python:3.11-slim

# Set the PATH environment variable to include user's local binary directory
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
    && rm -rf /var/lib/apt/lists/* # Clean up the package lists to reduce image size

# Set the working directory to /app
WORKDIR /app

# Clone the lib-tcpdump-processing repository
RUN git clone https://github.com/mbakholdina/lib-tcpdump-processing.git /app/libtcpdump

# Change the working directory to the cloned repository
WORKDIR /app/libtcpdump

# Install the Python package in the user's local directory
RUN pip install --user .

# Clone the SRT repository
RUN git clone https://github.com/Haivision/srt.git /app/srt

# Change the working directory to the SRT repository
WORKDIR /app/srt

# Build the SRT project
RUN cmake . && make

# Change the working directory back to /app
WORKDIR /app

# Copy the current directory contents into the container's /app directory
COPY . .

# Install the Python dependencies listed in docker_requirements.txt in the user's local directory
RUN pip install --user -r docker_dev_requirements.txt

# Create a symbolic link to the srt-live-transmit executable in the user's local binary directory
RUN ln -s /app/srt/srt-live-transmit /root/.local/bin

# Expose port 8501 for the Streamlit application
EXPOSE 8501
