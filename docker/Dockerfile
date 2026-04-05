# CUDA-based trainer image for local LoRA fine-tuning on NVIDIA GPUs (including legacy K80 setups).
# Focus: reproducibility via pinned Python dependencies.

FROM nvidia/cuda:11.3.1-cudnn8-runtime-ubuntu20.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/workspace/.cache/huggingface \
    HF_DATASETS_CACHE=/workspace/.cache/huggingface/datasets \
    TRANSFORMERS_CACHE=/workspace/.cache/huggingface/transformers

# Minimal OS + Python runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    curl \
    ca-certificates \
    tini \
 && ln -sf /usr/bin/python3 /usr/bin/python \
 && python -m pip install --upgrade \
    pip==24.0 \
    setuptools==69.2.0 \
    wheel==0.42.0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Install pinned training stack
COPY docker/requirements.txt /tmp/requirements.txt
RUN grep -v '^peft==' /tmp/requirements.txt > /tmp/requirements.core.txt \
 && python -m pip install --no-cache-dir -r /tmp/requirements.core.txt \
 && python -m pip install --no-cache-dir --no-deps peft==0.3.0 \
 && python -c "import torch, transformers, datasets, accelerate, peft, safetensors, yaml, sentencepiece; print('import-sanity-ok')" \
 && rm -f /tmp/requirements.txt /tmp/requirements.core.txt

# Prepare common runtime directories
RUN mkdir -p /workspace/src /workspace/configs /workspace/data /workspace/.cache/huggingface

# TensorBoard default port
EXPOSE 6006

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash"]
