#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Building Docker images for SERA repos ==="

echo "[1/3] Building sera-zephyr..."
docker build \
    --build-arg REPO_URL=https://github.com/zephyrproject-rtos/zephyr.git \
    --build-arg REPO_BRANCH=main \
    -t sera-zephyr:latest \
    -f "$SCRIPT_DIR/Dockerfile.generic" \
    "$SCRIPT_DIR" &

echo "[2/3] Building sera-nuttx..."
docker build \
    --build-arg REPO_URL=https://github.com/apache/nuttx.git \
    --build-arg REPO_BRANCH=master \
    -t sera-nuttx:latest \
    -f "$SCRIPT_DIR/Dockerfile.generic" \
    "$SCRIPT_DIR" &

echo "[3/3] Building sera-mbed-os..."
docker build \
    --build-arg REPO_URL=https://github.com/ARMmbed/mbed-os.git \
    --build-arg REPO_BRANCH=master \
    -t sera-mbed-os:latest \
    -f "$SCRIPT_DIR/Dockerfile.generic" \
    "$SCRIPT_DIR" &

wait

echo ""
echo "=== All images built ==="
docker images | grep sera-
