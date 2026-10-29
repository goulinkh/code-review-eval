FROM python@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*
COPY settings.json models.json /root/.pi/agent/
ENV PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1 PI_TELEMETRY=0
WORKDIR /workspace
