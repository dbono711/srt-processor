# srt-processor

## Overview

Interactive platform designed to serve as both a learning environment and a troubleshooting tool for analyzing Secure Reliable Transport (SRT) flows, enabling users to explore the intricacies of SRT, offering hands-on experience with live data and captured session files.

The platform is designed with flexibility in mind, allowing users to either upload Packet Capture (PCAP/PCAPNG) files containing SRT session data or initiate live SRT streams for real-time analysis. Through a combination of open-source tools and custom processing libraries, ```srt-processor``` provides a comprehensive view of SRT statistics, offering invaluable insights for network engineers, developers, and anyone interested in mastering SRT protocols.

## Prerequisites

- Docker installed on your local machine
- Git installed on your local machine (only required if [building locally](#building-the-docker-image-locally) or [development](#setting-up-development-environment-with-vs-code-development-containers))

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
    docker run -d -p 8501:8501/tcp -p 9000-9100:9000-9100/udp --cap-add=NET_ADMIN srt-processor
    ```

## Pulling the Docker Image from Docker Hub

Alternatively, you can pull the pre-built Docker image from Docker Hub:

1. Pull the Docker image from Docker Hub:

    ```shell
    docker pull dbono711/srt-processor:latest
    ```

2. Run the Docker container with port forwarding (adjust accordingly for mapping to available ports on your host). Note that the ```--cap-add=NET_ADMIN``` argument is required in order to utilize the network emulation options.

    ```shell
    docker run -d -p 8501:8501/tcp -p 9000-9100:9000-9100/udp --cap-add=NET_ADMIN dbono711/srt-processor:latest
    ```

## Accessing the Application

After starting the Docker container, you can access the Streamlit application by navigating to: ```http://<host ip>:8501```

## Setting Up Development Environment with VS Code Development Containers

This repository includes a .devcontainer folder for creating a consistent and reproducible development environment using VS Code Development Containers. Follow the steps below to set up and use the development environment in your own VS Code instance:

### Development Prerequisites

Before proceeding, ensure you have the following installed:

- Docker
- Visual Studio Code
- Remote - Containers extension for VS Code

### Steps to Set Up and Use the Development Container

1. Clone the Repository

Clone the repository to your local machine using the following command:

```git clone https://github.com/dbono711/srt-processor.git```

2. Open the Repository in VS Code

Navigate to the cloned repository folder and open it in VS Code:

```shell
cd srt-processor
code .
```

3. Reopen in Container

- Once the repository is open in VS Code, press F1 to open the command palette.
- Type and select Remote-Containers: Reopen in Container.

Alternatively, you can click on the green button at the bottom-left corner of the VS Code window and select Reopen in Container.

4. Wait for the Container to Build

VS Code will use the configuration in the .devcontainer folder to build and start a Docker container. This process might take a few minutes, especially the first time, as it needs to pull the Docker image and set up the environment.

Once the container is ready, you will be connected to the development environment inside the container. You can now start coding and utilize the development tools configured in the container. To run the Streamlit applicaiton, simply open up a ```New Terminal``` in the VS Code development container and run ```streamlit run --client.toolbarMode developer Home.py```. Note that the [devcontainer.json](.devcontainer/devcontainer.json) file is only forwarding ports 8501 and 9000. Adjust accordingly for your host.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
