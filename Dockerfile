# Use a base Ubuntu as required by the PDF
FROM ubuntu:22.04

# Avoid prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# Install Python and networking tools
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    iproute2 \
    tcpdump \
    tshark \
    iputils-ping \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Create logs directory
RUN mkdir -p logs

# Default command
CMD ["python3", "server.py", "--mode", "tcp"]
