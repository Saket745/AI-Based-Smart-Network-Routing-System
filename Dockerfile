# Stage 1: Build & Compile package
FROM python:3.10-slim@sha256:a78e4529630cfe8c5199cafd6e0c28ee1579a13f86274396d8b6b2d80367aa3a AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

# Install build dependencies and build package distributions
RUN pip install --no-cache-dir build && python -m build

# Stage 2: Minimal runtime image
FROM python:3.10-slim@sha256:a78e4529630cfe8c5199cafd6e0c28ee1579a13f86274396d8b6b2d80367aa3a

LABEL org.opencontainers.image.source="https://github.com/Saket745/AI-Based-Smart-Network-Routing-System"
LABEL org.opencontainers.image.description="AI-Based Smart Network Routing System (nroute)"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Create a non-root user and group
RUN groupadd -g 10001 nroute \
    && useradd -u 10001 -g nroute -m -s /sbin/nologin nroute \
    && chown -R nroute:nroute /app

# Copy the built wheel from builder stage
COPY --from=builder --chown=nroute:nroute /app/dist/*.whl ./

# Switch to the non-root user
USER nroute

# Install the wheel package locally
RUN pip install --user --no-cache-dir *.whl \
    && rm *.whl

# Ensure local user bin is on path (where the wheel installs the entry points)
ENV PATH="/home/nroute/.local/bin:${PATH}"

# Expose FastAPI port
EXPOSE 8000

# Add a healthcheck instruction to monitor API server status securely
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python3 -c 'import urllib.request, os; t=os.environ.get("NROUTE_API_TOKEN") or os.environ.get("NROUTE_GENERAL_API_TOKEN") or ""; req=urllib.request.Request("http://localhost:8000/api/health"); req.add_header("Authorization", "Bearer "+t) if t else None; urllib.request.urlopen(req, timeout=2)' || exit 1

# Expose CLI globally
ENTRYPOINT ["nroute"]
CMD ["--help"]
