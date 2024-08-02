# srt-processor

## Overview

```srt-processor``` is an interactive [Streamlit](https://streamlit.io/) application for presenting statistics about SRT flows. It offers the user the ability to either a upload a ```.pcap(ng)``` file containing an SRT session for processing using the [lib-tcpdump-processing](https://github.com/mbakholdina/lib-tcpdump-processing) open source library, or spawn an [srt-live-transmit](https://github.com/Haivision/srt/blob/master/docs/apps/srt-live-transmit.md) process to receive a flow.

## Prerequisites

- Docker installed on your local machine
- Git installed on your local machine

## Building the Docker Image Locally

To build the Docker image locally from the Dockerfile included in this repository, follow these steps:

1. Clone the repository:

    ```shell
    git clone https://github.com/yourusername/your-repo-name.git
    cd your-repo-name
    ```

2. Build the Docker image:

    ```shell
    docker build -t your-image-name .
    ```

3. Run the Docker container with port forwarding:

    ```shell
    docker run -d -p 8501:8501 your-image-name
    ```

## Pulling the Docker Image from Docker Hub

Alternatively, you can pull the pre-built Docker image from my Docker Hub:

1. Pull the Docker image from Docker Hub:

    ```shell
    docker pull yourdockerhubusername/your-image-name:latest
    ```

2. Run the Docker container with port forwarding:

    ```shell
    docker run -d -p 8501:8501 yourdockerhubusername/your-image-name:latest
    ```

## Accessing the Application

After starting the Docker container, you can access the Streamlit application by navigating to: ```http://localhost:8501```

## Additional Information

- Ensure that port 8501 is not being used by other applications on your local machine.

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

```git clone https://github.com/your-username/your-repo-name.git```

2. Open the Repository in VS Code

Navigate to the cloned repository folder and open it in VS Code:

```shell
cd your-repo-name
code .
```

3. Reopen in Container

- Once the repository is open in VS Code, press F1 to open the command palette.
- Type and select Remote-Containers: Reopen in Container.

Alternatively, you can click on the green button at the bottom-left corner of the VS Code window and select Reopen in Container.

4. Wait for the Container to Build

VS Code will use the configuration in the .devcontainer folder to build and start a Docker container. This process might take a few minutes, especially the first time, as it needs to pull the Docker image and set up the environment.

Once the container is ready, you will be connected to the development environment inside the container. You can now start coding and utilize the development tools configured in the container.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
