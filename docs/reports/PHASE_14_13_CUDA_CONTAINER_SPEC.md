# YORVYN PHASE 14.13 — WORKSTREAM I.2: REMOTE CUDA DEPLOYMENT SPECIFICATION

**Project:** YORVYN Fashion Intelligence & 3D Virtual Try-On Platform  
**Phase:** 14.13 Workstream I.2  
**Audit Standard:** Principal ML Infrastructure Engineer & GPU Systems Architect  
**Baseline Git Commit:** `7139fc7eea4e1f890e28da9140db2e8550081267`  
**Deployment Classification:** `BLOCKED (Deployment-Ready Specification Authored; Physical Cloud CUDA Execution Pending Authorization)`  

---

## 1. COMPATIBILITY & RUNTIME MATRIX

To ensure reproducible, bug-free execution on NVIDIA data center GPUs, the software and driver stack is pinned to the following verified matrix:

| Layer | Component | Target Specification | Minimum Supported |
|---|---|---|---|
| **Base OS** | Ubuntu LTS | Ubuntu 22.04 LTS (Jammy) | Ubuntu 20.04 LTS |
| **CUDA Runtime** | NVIDIA CUDA Toolkit | **12.1.1** (devel / runtime) | 12.0.0 |
| **NVIDIA Driver** | Data Center GPU Driver | **>= 530.30.02** | 525.60.13 (CUDA 12.0) |
| **Hardware** | Target NVIDIA Accelerator | **NVIDIA L4 (24GB)** / **A10G (24GB)** | NVIDIA T4 (16GB) |
| **Python** | Python Runtime | **3.10.12** | 3.9.18 |
| **Deep Learning** | PyTorch & Torchvision | `torch==2.3.0+cu121`, `torchvision==0.18.0+cu121` | `torch>=2.2.0` |
| **Web Framework**| FastAPI / Uvicorn | `fastapi==0.111.0`, `uvicorn[standard]==0.29.0` | `fastapi>=0.100.0` |
| **Vision & Geometry** | Core Packages | `opencv-python-headless==4.9.0.80`, `trimesh==4.3.2`, `pygltflib==1.16.2`, `scipy==1.13.0` | — |

---

## 2. DOCKERFILE.CUDA (PRODUCTION CONTAINER BUILD SPECIFICATION)

```dockerfile
# ==============================================================================
# YORVYN REMOTE NEURAL 3D RECONSTRUCTION WORKER (NVIDIA CUDA 12.1)
# ==============================================================================
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04 AS base

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TORCH_CUDA_ARCH_LIST="8.0;8.6;8.9;9.0" \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3.10-distutils \
    python3-pip \
    curl \
    libgl1 \
    libglib2.0-0 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set up non-root application user
RUN groupadd -g 10001 yorvyn && \
    useradd -u 10001 -g yorvyn -m -s /bin/bash appuser

WORKDIR /app

# Install Python packages
COPY backend/requirements.txt /app/requirements.txt
RUN pip3 install --upgrade pip setuptools wheel && \
    pip3 install --index-url https://download.pytorch.org/whl/cu121 \
        torch==2.3.0+cu121 \
        torchvision==0.18.0+cu121 && \
    pip3 install -r /app/requirements.txt

# Copy application source
COPY --chown=appuser:yorvyn backend /app/backend
COPY --chown=appuser:yorvyn models /app/models

# Storage directory permissions
RUN mkdir -p /app/models/generated_3d/staging_jobs/jobs && \
    chown -R appuser:yorvyn /app/models

# Switch to non-root execution
USER appuser

# Health check probe
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://127.0.0.1:8088/health || exit 1

EXPOSE 8088

# Entrypoint with graceful SIGTERM trap
ENTRYPOINT ["python3", "-m", "uvicorn", "backend.app.services.garments.reconstruction.neural.staging_worker:app"]
CMD ["--host", "0.0.0.0", "--port", "8088", "--workers", "1", "--log-level", "info"]
```

---

## 3. DOCKER-COMPOSE.CUDA.YML (LOCAL CUDA TESTING)

```yaml
version: '3.8'

services:
  yorvyn-cuda-worker:
    build:
      context: .
      dockerfile: Dockerfile.cuda
    image: yorvyn/cuda-reconstruction-worker:14.13
    container_name: yorvyn-cuda-inference
    restart: unless-stopped
    ports:
      - "127.0.0.1:8088:8088"
    environment:
      - HOST=0.0.0.0
      - PORT=8088
      - ALLOW_REMOTE_BIND=1
      - GARMENT_AI_REMOTE_API_KEY=${GARMENT_AI_REMOTE_API_KEY:-yorvyn_staging_key_v14_6}
      - GARMENT_AI_REMOTE_SIGNING_SECRET=${GARMENT_AI_REMOTE_SIGNING_SECRET:-yorvyn-secret-key}
      - NVIDIA_VISIBLE_DEVICES=all
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 16G
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ./models/generated_3d/staging_jobs:/app/models/generated_3d/staging_jobs
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"
```

---

## 4. KUBERNETES POD & PROBE SPECIFICATION (CLOUD EKS/GKE DEPLOYMENT)

### 4.1 Liveness & Readiness Probes
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8088
  initialDelaySeconds: 45
  periodSeconds: 15
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health
    port: 8088
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 2
```

### 4.2 Resource Limits & GPU Allocation
```yaml
resources:
  requests:
    cpu: "2000m"
    memory: "8Gi"
    nvidia.com/gpu: 1
  limits:
    cpu: "4000m"
    memory: "16Gi"
    nvidia.com/gpu: 1
```

### 4.3 Graceful Termination
The pod lifecycle includes a 30-second `terminationGracePeriodSeconds` to drain active inference passes before `SIGKILL`.

---

## 5. INDEPENDENT VERIFICATION RULE

> [!IMPORTANT]
> **Strict Provenance Assertion:** In strict adherence to Phase 14.13 rules, this specification is deployment-ready, but the remote cloud CUDA status remains **`BLOCKED`** in all official audit reports until authenticated execution on physical NVIDIA GPU hardware is verified.
