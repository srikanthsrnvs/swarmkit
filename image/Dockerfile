# One sandbox per swarm agent: CUDA devel toolchain + node + pi + agent-network (pi adapter, anet CLI) + uv + OptMem
# + the swarmkit Python package (OpenAI Agents SDK runner). Build with the REPO ROOT as the context (.dockerignore
# there keeps it to image/agent-network, swarmkit/, pyproject.toml, README.md) after staging a pinned tag:
#   bin/stage-agent-network.sh v0.2.0
#   docker build -t swarmkit-agent:v0.2.0 --build-arg UID=$(id -u) -f image/Dockerfile .      (= `swarmctl build`)
# CPU-only box: --build-arg BASE_IMAGE=ubuntu:24.04 (same image minus nvcc; CUDA_HOME paths are then unused).
# x86_64 and arm64 both build (the Mac sandbox uses the CPU base).
ARG BASE_IMAGE=nvidia/cuda:12.9.1-devel-ubuntu24.04
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive TZ=UTC LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl wget gnupg git git-lfs openssh-client sudo tmux htop jq ripgrep \
      build-essential pkg-config ninja-build ccache python3 python3-venv python3-dev python3-pip \
      libssl-dev libcurl4-openssl-dev zlib1g-dev libgomp1 procps less vim-tiny unzip zstd rsync \
      iproute2 lsof strace file bc \
    && rm -rf /var/lib/apt/lists/*

# recent cmake (Ubuntu 24.04 ships 3.28; some engines want newer)
RUN curl -fsSL https://apt.kitware.com/keys/kitware-archive-latest.asc | gpg --dearmor -o /usr/share/keyrings/kitware.gpg \
    && echo 'deb [signed-by=/usr/share/keyrings/kitware.gpg] https://apt.kitware.com/ubuntu/ noble main' > /etc/apt/sources.list.d/kitware.list \
    && apt-get update && apt-get install -y --no-install-recommends cmake && rm -rf /var/lib/apt/lists/* && cmake --version

# node 24 + pi 1.1.0 (the version verified with the agent-network pi adapter)
ARG PI_VERSION=1.1.0
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && apt-get install -y nodejs && rm -rf /var/lib/apt/lists/* \
    && npm i -g @earendil-works/pi-coding-agent@${PI_VERSION} && pi --version

# uv / uvx for everyone
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh && uv --version

# the agent user: same uid as the host user so bind-mounted files stay editable on both sides
ARG UID=1000
RUN (getent passwd ${UID} && userdel -r "$(getent passwd ${UID} | cut -d: -f1)" || true) \
    && useradd -m -s /bin/bash -u ${UID} agent \
    && echo 'agent ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/agent && chmod 440 /etc/sudoers.d/agent \
    && mkdir -p /swarm/me /swarm/shared /opt/agent-network /opt/swarmkit && chown -R agent:agent /swarm /opt/agent-network /opt/swarmkit

# `anet` for every user and every shell in the sandbox (root-installed wrapper; the CLI itself runs as whoever calls it)
RUN printf '#!/bin/sh\nexec node /opt/agent-network/packages/cli/bin/anet.mjs "$@"\n' > /usr/local/bin/anet && chmod 755 /usr/local/bin/anet

USER agent
# agent-network at the pinned tag (staged by bin/stage-agent-network.sh), built in place
COPY --chown=agent:agent image/agent-network /opt/agent-network
WORKDIR /opt/agent-network
RUN npm ci --no-audit --no-fund && npm run build \
    && node -e 'import("@xmtp/node-sdk").then(()=>console.log("xmtp native binding ok (" + process.arch + ")"))' \
    && anet 2>&1 | head -1 \
    && rm -rf /home/agent/.npm

# swarmkit's Python side: the OpenAI Agents SDK runner (python -m swarmkit.run) in its own venv; the anet Python
# package is installed from the staged tag when that tag ships python/ (v0.3.0+), else the runner's built-in client is used
COPY --chown=agent:agent pyproject.toml README.md /opt/swarmkit/
COPY --chown=agent:agent swarmkit /opt/swarmkit/swarmkit
RUN cd /opt/swarmkit && uv venv -q .venv && uv pip install -q -p .venv/bin/python -e . \
    && { [ -d /opt/agent-network/python ] && uv pip install -q -p .venv/bin/python -e /opt/agent-network/python || true; } \
    && .venv/bin/python -c 'import agents, swarmkit; print("openai-agents", agents.__version__, "swarmkit", swarmkit.__version__)' \
    && rm -rf /home/agent/.cache/uv

# OptMem (memo); each agent's memories live in /swarm/me/memory via MEMORY_DIR
RUN curl -fsSL https://raw.githubusercontent.com/VictorTaelin/OptMem/main/install.sh | sh && test -x /home/agent/.optmem/memo

ENV PATH=/usr/local/cuda/bin:/opt/swarmkit/.venv/bin:/home/agent/.local/bin:$PATH \
    HF_HOME=/swarm/shared/hf \
    AGENT_MEMO=/home/agent/.optmem/memo \
    MEMORY_DIR=/swarm/me/memory \
    CCACHE_DIR=/swarm/me/.ccache
WORKDIR /swarm/me
CMD ["sleep", "infinity"]
