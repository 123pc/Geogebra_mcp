FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y nodejs npm --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY package.json package-lock.json ./
RUN npm install

COPY *.py *.js ./

ENV GEOGEBRA_CDP_PORT=9222

CMD ["python", "geogebra_mcp_server.py"]
