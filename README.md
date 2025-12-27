# logging-service

This repository contains a **centralized logging setup** for a cloud-based crypto tracker application running on **Kubernetes (Azure AKS)**.

The goal is to collect, store, and analyze logs from all services in a **single, self-hosted, low-cost logging system**.

---

## Stack

- **Flask services** – log to stdout (preferably structured JSON)
- **Fluent Bit** – collects logs from Kubernetes pods
- **OpenSearch** – stores and indexes logs
- **OpenSearch Dashboards** – log visualization and analysis
- **Alerting** – planned (via OpenSearch Alerting)

---

## Architecture
```
Flask Services (stdout)
        ↓
Fluent Bit (DaemonSet)
        ↓
OpenSearch (StatefulSet)
        ↓
OpenSearch Dashboards (UI)
```

---

## Project Structure

```
logging-service/
├── README.md                   # This file
├── Dockerfile                  # Docker image for sample app
├── requirements.txt            # Python dependencies
├── app.py                      # Sample Flask app with structured JSON logging
└── k8s/
    ├── opensearch.yaml          # OpenSearch StatefulSet + ConfigMap
    ├── dashboards.yaml          # OpenSearch Dashboards Deployment
    └── fluent-bit.yaml          # Fluent Bit DaemonSet + ConfigMap + RBAC
```

---

## Quick Start

### 1. Deploy to Kubernetes

```bash
# Create namespace and deploy OpenSearch
kubectl apply -f k8s/01-opensearch.yaml

# Deploy OpenSearch Dashboards
kubectl apply -f k8s/02-dashboards.yaml

# Deploy Fluent Bit for log collection
kubectl apply -f k8s/03-fluent-bit.yaml

# Deploy sample app
kubectl apply -f k8s/04-sample-app.yaml

# Verify all pods are running
kubectl get pods -n logging
```

### 2. Access OpenSearch Dashboards

```bash
# Port-forward to OpenSearch Dashboards
kubectl port-forward -n logging svc/opensearch-dashboards 5601:5601

# Open browser: http://localhost:5601
# Default credentials: admin / OpenSearchPassword123!
```

---

## Testing the Setup

### View Logs in Dashboards

1. Open OpenSearch Dashboards at `http://localhost:5601`
2. Go to **Discover** → Create Index Pattern
3. Use pattern `app-logs-*`
4. Set timestamp field to `timestamp`
5. Click **Create index pattern**
6. Browse logs in the **Discover** tab

---

## How to Add Logging to Python App

### 1. Use Structured JSON Logging

See [app.py](app.py) for a complete example. Key points:

- Create a custom `JSONFormatter` that inherits from `logging.Formatter`
- Include timestamp, level, logger name, message, and context fields
- Add request/exception details when available
- **Always log to stdout**, not files

### 2. Example __init__.py

```python
from flask import Flask

def create_app():
    app = Flask(__name__)
    
    # Set up request logging middleware
    from app.utils.logger import setup_request_logging
    setup_request_logging(app)
    
    return app
```

### 3. Log to stdout

- Always log to **stdout** or **stderr**, not files
- Kubernetes/Docker will automatically capture container output
- Fluent Bit collects logs from `/var/log/containers/` and forwards to OpenSearch

---

## What Is Logged

- Application crashes and errors (5xx, exceptions)
- Suspicious behavior (e.g. repeated failed auth attempts)
- Basic performance data (slow requests)
- Custom application events

---

## Log Retention

- Logs are stored for **several months** (configurable via ILM policies)
- Index naming: `app-logs-YYYY.MM.DD` (daily rotation)
- Old logs can be removed using OpenSearch lifecycle policies

---

## Fluent Bit Configuration

The Fluent Bit DaemonSet:
- Runs on **every node** as a DaemonSet
- Collects container logs from `/var/log/containers/`
- Enriches logs with **Kubernetes metadata** (namespace, pod name, container name, labels)
- Sends to OpenSearch on **port 9200**
- Retries failed sends (up to 5 times) with backoff

**Key features:**
- Memory buffer limits to prevent memory leaks
- Automatic restart on failure
- Tolerations for master nodes
- Service account with minimal RBAC permissions

---

## OpenSearch Configuration

- **Single-node cluster** for dev/test (can scale to 3+ nodes)
- **No authentication** by default (suitable for dev only)
- **1 primary shard, 0 replicas** per index
- **Persistent storage** via StatefulSet with 5GB PVC
- **Daily index rotation** via `logstash_prefix` in Fluent Bit

### Enable Security (Production)

To add authentication:

1. Edit `k8s/01-opensearch.yaml`: Set `plugins.security.disabled: false`
2. Generate security certificates using OpenSearch security plugin
3. Update Fluent Bit credentials in `k8s/03-fluent-bit.yaml`
4. Configure HTTPS for Dashboards

---

## Why This Approach

- Fully **self-hosted** and **open-source** (no vendor lock-in)
- Lightweight and **Kubernetes-native**
- Cheaper and simpler than a full ELK stack
- Easy to extend with alerting and custom dashboards later
- Suitable for educational and small-scale deployments

---

## Troubleshooting

### Check OpenSearch Cluster Status

```bash
kubectl exec -n logging opensearch-0 -- curl https://localhost:9200/_cluster/health
```

### View Fluent Bit Logs

```bash
kubectl logs -n logging -l app=fluent-bit -f
```

### Check Sample App Logs

```bash
kubectl logs -n logging -l app=sample-app -f
```

### Verify Index Creation

```bash
kubectl exec -n logging opensearch-0 -- curl https://localhost:9200/_cat/indices
```

### Port-forward to OpenSearch

```bash
kubectl port-forward -n logging svc/opensearch 9200:9200
curl https://localhost:9200/_cat/health
```
