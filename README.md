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
    ├── 01-opensearch.yaml          # OpenSearch StatefulSet + ConfigMap
    ├── 02-dashboards.yaml          # OpenSearch Dashboards Deployment
    ├── 03-fluent-bit.yaml          # Fluent Bit DaemonSet + ConfigMap + RBAC
    ├── 04-sample-app.yaml          # Sample app Deployment + Service
    └── init-opensearch.sh          # Script to initialize OpenSearch indices
```

---

## Quick Start

### 1. Build and Push Sample App Docker Image

```bash
# Build the sample Flask app image
docker build -t crypto-tracker/logging-service:latest .

# For local K8s clusters, load image directly:
# minikube image load crypto-tracker/logging-service:latest
# kind load docker-image crypto-tracker/logging-service:latest
```

### 2. Deploy to Kubernetes

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

### 3. Initialize OpenSearch

```bash
# Option A: Run init script from outside cluster
chmod +x k8s/init-opensearch.sh
./k8s/init-opensearch.sh

# Option B: Port-forward and curl manually
kubectl port-forward -n logging svc/opensearch 9200:9200

# In another terminal, run:
curl -k -X PUT "https://localhost:9200/_index_template/app-logs-template" \
  -H "Content-Type: application/json" \
  -u "admin:OpenSearchPassword123!" \
  -d '{
    "index_patterns": ["app-logs-*"],
    "template": {
      "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0
      },
      "mappings": {
        "properties": {
          "timestamp": { "type": "date" },
          "level": { "type": "keyword" },
          "logger": { "type": "keyword" },
          "message": { "type": "text" },
          "module": { "type": "keyword" },
          "function": { "type": "keyword" },
          "line": { "type": "long" },
          "exception": { "type": "text" }
        }
      }
    }
  }'
```

### 4. Access OpenSearch Dashboards

```bash
# Port-forward to OpenSearch Dashboards
kubectl port-forward -n logging svc/opensearch-dashboards 5601:5601

# Open browser: http://localhost:5601
# Default credentials: admin / OpenSearchPassword123!
```

---

## Testing the Setup

### Generate Sample Logs

```bash
# Port-forward to sample app
kubectl port-forward -n logging svc/sample-app 5000:5000

# In another terminal, generate some logs:
curl http://localhost:5000/api/data
curl http://localhost:5000/api/error  # Will generate error logs
curl http://localhost:5000/health
```

### View Logs in Dashboards

1. Open OpenSearch Dashboards at `http://localhost:5601`
2. Go to **Discover** → Create Index Pattern
3. Use pattern `app-logs-*`
4. Set timestamp field to `timestamp`
5. Click **Create index pattern**
6. Browse logs in the **Discover** tab

---

## How to Add Logging to Your Python App

### 1. Use Structured JSON Logging

See [app.py](app.py) for a complete example. Key points:

- Create a custom `JSONFormatter` that inherits from `logging.Formatter`
- Include timestamp, level, logger name, message, and context fields
- Add request/exception details when available
- **Always log to stdout**, not files

### 2. Example Integration

```python
import json
import logging
import sys
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)

# Configure logging
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logger = logging.getLogger(__name__)
logger.addHandler(handler)

# Use it
logger.info("Application started")
logger.error("An error occurred", exc_info=True)
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
kubectl exec -n logging opensearch-0 -- curl -k -u admin:OpenSearchPassword123! https://localhost:9200/_cluster/health
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
kubectl exec -n logging opensearch-0 -- curl -k -u admin:OpenSearchPassword123! https://localhost:9200/_cat/indices
```

### Port-forward to OpenSearch

```bash
kubectl port-forward -n logging svc/opensearch 9200:9200
curl -k -u admin:OpenSearchPassword123! https://localhost:9200/_cat/health
```

---

## Status

- ✅ Centralized logging architecture defined
- ✅ Sample Flask app with structured JSON logging
- ✅ Kubernetes manifests for OpenSearch, Dashboards, and Fluent Bit
- ✅ Index templates and initialization script
- ⏳ Alerting rules and automation (planned)
- ⏳ TLS/mTLS security hardening (planned)
- ⏳ Helm chart packaging (planned)

---

## Notes

This setup is designed for **educational and development purposes**. It focuses on simplicity, clarity, and low operational cost. For production use:
- Add authentication and TLS encryption
- Set up resource quotas and pod disruption budgets
- Configure alerting and notification rules
- Implement automated backups
- Monitor cluster health and log volume