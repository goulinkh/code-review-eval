FROM code-review-pilot:20261025T221002Z
SHELL ["/bin/bash", "-lc"]
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | env -u NODE_VERSION bash && export NVM_DIR="$HOME/.nvm" && \. "$NVM_DIR/nvm.sh" || true && command -v nvm &>/dev/null || { echo 'Error: NVM failed to load' >&2; exit 1; } && nvm install 22 && nvm alias default 22 && npm -v && npm install -g --ignore-scripts @earendil-works/pi-coding-agent@1.1.0
COPY settings.json models.json /root/.pi/agent/
WORKDIR /workspace
