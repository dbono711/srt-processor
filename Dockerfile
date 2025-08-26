# Multi-stage build for optimized SRT Processor image

# ============================================================================
# Build Stage: Compile SRT tools and dependencies
# ============================================================================
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    cmake \
    build-essential \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Pin specific commits for reproducible builds
ARG LIBTCPDUMP_COMMIT=master
ARG SRT_COMMIT=master

# Clone and build lib-tcpdump-processing
RUN git clone https://github.com/mbakholdina/lib-tcpdump-processing.git /opt/libtcpdump
WORKDIR /opt/libtcpdump
RUN git checkout ${LIBTCPDUMP_COMMIT}
RUN pip install --user .

# Install Python dependencies that require compilation
COPY docker_requirements.txt /tmp/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --user -r /tmp/docker_requirements.txt

# Clone and build SRT tools
RUN git clone https://github.com/Haivision/srt.git /opt/srt
WORKDIR /opt/srt

# Define SRT versions to build
ARG SRT_VERSIONS="v1.4.4 v1.5.0 v1.5.3"

# Build SRT versions with parallel compilation
RUN for version in ${SRT_VERSIONS}; do \
    git checkout $version && \
    mkdir -p build_$version && \
    cd build_$version && \
    cmake .. && \
    make -j$(nproc) && \
    cd .. ; \
    done

# Create a dedicated directory for SRT binaries
RUN mkdir -p /opt/srt-binaries
RUN for version in ${SRT_VERSIONS}; do \
    cp /opt/srt/build_$version/srt-live-transmit /opt/srt-binaries/srt-live-transmit-$version; \
    done

# ============================================================================
# Runtime Stage: Minimal production image
# ============================================================================
FROM python:3.11-slim AS runtime

# Create non-root user for security
RUN groupadd -r srtuser && useradd -r -g srtuser srtuser

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    tshark \
    ffmpeg \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Set up directories and permissions
WORKDIR /app
RUN chown srtuser:srtuser /app

# Copy SRT binaries from builder stage
COPY --from=builder /opt/srt-binaries/* /usr/local/bin/
RUN chmod +x /usr/local/bin/srt-live-transmit-*

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/srtuser/.local
RUN chown -R srtuser:srtuser /home/srtuser/.local

# Set PATH for non-root user
ENV PATH="/home/srtuser/.local/bin:${PATH}"

# Copy application code
COPY --chown=srtuser:srtuser . .

# Switch to non-root user
USER srtuser

# Expose ports
EXPOSE 8501/tcp
EXPOSE 9000-9100/udp

# Run Streamlit application
CMD ["streamlit", "run", "Home.py", "--server.address=0.0.0.0", "--server.port=8501"]
