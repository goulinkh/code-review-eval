FROM code-review-sweep:20261025t225616z
COPY npm-cached /tmp/npm-cached
RUN for npm in /root/.nvm/versions/node/*/bin/npm; do mv "$npm" "$npm-real"; cp /tmp/npm-cached "$npm"; chmod +x "$npm"; done
COPY settings.json models.json /root/.pi/agent/
WORKDIR /workspace
