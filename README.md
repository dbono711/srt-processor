# srt-processor

## Overview

Interactive platform designed to serve as both a learning environment and a troubleshooting tool for analyzing Secure Reliable Transport (SRT) flows, enabling users to explore the intricacies of SRT through live streaming sessions.

The application allows users to initiate live SRT streams for real-time analysis. Through a combination of open-source tools and custom processing libraries, ```srt-processor``` provides a comprehensive view of SRT statistics, offering invaluable insights for network engineers, developers, and anyone interested in learning SRT.

## Prerequisites

- Docker installed on your local machine
- Git installed on your local machine (only required if [building locally](#building-the-docker-image-locally) or [development](#development))

## Container Ports

The container exposes the following ports for connectivity:

- (TCP) port 8501 for accessing the Streamlit application
- (UDP) ports 9000-9100 for SRT sessions

## Building the Docker Image Locally

To build the Docker image locally from the Dockerfile included in this repository, follow these steps:

1. Clone the repository:

    ```shell
    git clone https://github.com/dbono711/srt-processor.git
    cd srt-processor
    ```

2. Build the Docker image:

    ```shell
    docker build -t srt-processor .
    ```

3. Run the Docker container with port forwarding (adjust accordingly for mapping to available ports on your host). Note that the ```--cap-add=NET_ADMIN``` argument is required in order to utilize the network emulation options.

    ```shell
    docker run -d -p 8501:8501/tcp -p 9000-9100:9000-9100/udp --cap-add=NET_ADMIN --name srt-processor srt-processor:latest
    ```

## Pulling the Docker Image from Docker Hub

Alternatively, you can pull the pre-built Docker image from Docker Hub:

1. Pull the Docker image from Docker Hub:

    ```shell
    docker pull dbono711/srt-processor:latest
    ```

2. Run the Docker container with port forwarding (adjust accordingly for mapping to available ports on your host). Note that the ```--cap-add=NET_ADMIN``` argument is required in order to utilize the network emulation options.

    ```shell
    docker run -d -p 8501:8501/tcp -p 9000-9100:9000-9100/udp --cap-add=NET_ADMIN --name srt-processor dbono711/srt-processor:latest
    ```

## Accessing the Application

After starting the Docker container, you can access the Streamlit application by navigating to: ```http://<host ip>:8501```

## Example: Streaming to SRT Processor as a listener

You can use FFmpeg to stream media to the SRT Processor application when it's configured as a listener. Here's an example of how to set up an SRT caller flow to stream video to the application:

1. First, ensure the SRT Processor application is running and configured in Listener mode on the desired port (e.g., 9000).

2. Use the following FFmpeg command to stream a video file to the SRT Processor:

    ```shell
    docker run --rm -v $(pwd):$(pwd) -w $(pwd) \
        --name ffmpeg-stream jrottenberg/ffmpeg:4.4-ubuntu \
        -stats \
        -re \
        -i sample_1280x720_surfing_with_audio.mp4 \
        -c:v libx264 -b:v 2500k -g 60 -keyint_min 60 \
        -profile:v main \
        -preset fast \
        -f mpegts "srt://<container-ip>:9000?pkt_size=1316"
    ```

    Replace `<container-ip>` with the IP address of your SRT Processor container, and adjust the input file path as needed.

    Assumes a file named ```sample_1280x720_surfing_with_audio.mp4``` is present in the current directory. Replace with your own file path as needed.

3. Command breakdown:
   - `-stats`: Shows encoding progress statistics
   - `-re`: Reads input at native frame rate (simulates a live source)
   - `-c:v libx264`: Uses H.264 video codec
   - `-b:v 2500k`: Sets video bitrate to 2500 kbps
   - `-g 60 -keyint_min 60`: Sets GOP size and minimum keyframe interval to 60 frames
   - `-profile:v main`: Uses the "main" H.264 profile
   - `-preset fast`: Balances encoding speed and compression efficiency
   - `-f mpegts`: Sets output format to MPEG Transport Stream
   - `pkt_size=1316`: Optimizes SRT packet size for network transmission

4. Once the stream starts, you should see the SRT statistics updating in the SRT Processor web interface.

## Development

This repository includes a [docker-compose.dev.yml](docker-compose.dev.yml) file for creating a consistent and reproducible development environment using Docker Compose.

### Development Prerequisites

Before proceeding, ensure you have the following installed:

- Docker

### Development Setup

1. Clone the Repository

Clone the repository to your local machine using the following command:

```git clone https://github.com/dbono711/srt-processor.git```

2. Start the Development Container

Navigate to the cloned repository folder and run the following command:

```shell
cd srt-processor
# Start development environment
make dev
```

3. View the Application

- Once the development environment is up and running, you can access the Streamlit application by navigating to: ```http://<host ip>:8501```

4. Stop the Development Container

- To stop the development container, run the following command:

```shell
make stop
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
