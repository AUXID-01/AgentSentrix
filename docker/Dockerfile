FROM python:3.11-slim

WORKDIR /app/target_repo

# Install basic OS utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Create simulated AWS directory & credentials
RUN mkdir -p /root/.aws
RUN echo "[default]\naws_access_key_id = AKIAIOSFODNN7EXAMPLE\naws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" > /root/.aws/credentials

# Copy simulated target repository workspace
COPY target_repo/ /app/target_repo/

# Default command
CMD ["tail", "-f", "/dev/null"]
