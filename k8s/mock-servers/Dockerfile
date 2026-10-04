FROM python:3.12-slim
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY k8s/mock-servers/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# GEW mock servers
COPY scenarios/gew/mock_infrastructure/mock_api_server.py .
COPY scenarios/gew/mock_infrastructure/mock_crm_server.py .
COPY scenarios/gew/mock_infrastructure/approval_server.py .

# TCW mock servers
COPY scenarios/tcw/mock_infrastructure/ml_endpoint.py .
COPY scenarios/tcw/mock_infrastructure/channel_adapter.py .

# SEC mock auth server — HTTP credential bleed probe
COPY k8s/mock-servers/mock_auth_server.py .

# Process runner — starts both HTTP and MCP server
COPY k8s/mock-servers/runner.py .

CMD ["python", "runner.py"]
