# Stage 1: Build & Compile package
FROM python:3.10-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

# Install build dependencies and build package distributions
RUN pip install --no-cache-dir build && python -m build

# Stage 2: Minimal runtime image
FROM python:3.10-slim

WORKDIR /app

# Copy the built wheel from builder stage
COPY --from=builder /app/dist/*.whl ./

# Install the wheel package locally
RUN pip install --no-cache-dir *.whl \
    && rm *.whl

# Expose CLI globally
ENTRYPOINT ["nroute"]
CMD ["--help"]
