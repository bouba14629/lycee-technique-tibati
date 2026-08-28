FROM node:22-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 python3-venv python3-pip \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN npm install -g corepack@latest \
  && corepack pnpm install \
  && corepack pnpm run build \
  && python3 -m venv /opt/ltt-venv \
  && /opt/ltt-venv/bin/pip install --no-cache-dir --upgrade pip \
  && /opt/ltt-venv/bin/pip install --no-cache-dir -r flask_app/requirements.txt

ENV NODE_ENV=production \
  LTT_FLASK_ENABLED=1 \
  LTT_PYTHON_BIN=/opt/ltt-venv/bin/python3

CMD ["node", "dist/index.js"]
