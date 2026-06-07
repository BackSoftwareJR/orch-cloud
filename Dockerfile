FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/root/.local/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    nodejs \
    npm \
    php-cli \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Composer (PHP dependency manager for Laravel projects)
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

# Install Cursor CLI (requires glibc — Ubuntu, not Alpine)
RUN curl https://cursor.com/install -fsS | bash \
    && cursor-agent --version \
    && ln -sf "$(command -v cursor-agent)" /usr/local/bin/agent

COPY scripts/cursor-agent-entrypoint.sh /usr/local/bin/cursor-agent-entrypoint.sh
RUN chmod +x /usr/local/bin/cursor-agent-entrypoint.sh

WORKDIR /workspace
