#!/usr/bin/env bash
#
# build_sera_container.sh
#
# Builds Docker images for the SERA/SVG pipeline targeting the OpenAirInterface5G codebase.
#
# For each commit SHA listed in configs/commits.json, this script builds a Docker image
# tagged as:
#     oai5g-sera:<commit_short_hash>
#
# It also builds a HEAD (latest) image tagged as:
#     oai5g-sera:latest
#
# Usage:
#     cd /path/to/sera          # project root (must contain openairinterface5g/ and configs/)
#     ./docker/build_sera_container.sh
#
# Prerequisites:
#     1. Docker must be installed and running.
#     2. The openairinterface5g/ directory must be a cloned git repo at the project root.
#     3. configs/commits.json must contain real commit SHAs (replace the placeholders).
#     4. jq must be installed (for JSON parsing).
#
# Notes:
#     - The build context is the sera project root so that COPY openairinterface5g/ works.
#     - Each per-commit image checks out the specified SHA inside the container.
#     - The :latest image uses HEAD (whatever commit is currently checked out locally).
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DOCKERFILE="$SCRIPT_DIR/Dockerfile.sera"
COMMITS_FILE="$PROJECT_ROOT/configs/commits.json"
REPO_CONFIG="$PROJECT_ROOT/configs/repo_config.json"

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker is not installed or not in PATH." >&2
    exit 1
fi

if ! command -v jq &>/dev/null; then
    echo "ERROR: jq is not installed. Install it with: brew install jq  (macOS) or apt-get install jq  (Linux)." >&2
    exit 1
fi

if [ ! -f "$DOCKERFILE" ]; then
    echo "ERROR: Dockerfile not found at $DOCKERFILE" >&2
    exit 1
fi

if [ ! -f "$COMMITS_FILE" ]; then
    echo "ERROR: commits.json not found at $COMMITS_FILE" >&2
    exit 1
fi

if [ ! -f "$REPO_CONFIG" ]; then
    echo "ERROR: repo_config.json not found at $REPO_CONFIG" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Load repo configuration
# ---------------------------------------------------------------------------
REPO_NAME=$(jq -r '.repo_name' "$REPO_CONFIG")
DOCKER_IMAGE_PREFIX=$(jq -r '.docker_image_prefix' "$REPO_CONFIG")
CONTAINER_REPO_PATH=$(jq -r '.container_repo_path // "/repo"' "$REPO_CONFIG")

if [ ! -d "$PROJECT_ROOT/$REPO_NAME/.git" ]; then
    echo "ERROR: $REPO_NAME/ does not appear to be a git repo at $PROJECT_ROOT/$REPO_NAME" >&2
    exit 1
fi

echo "Repo config:"
echo "  repo_name:           $REPO_NAME"
echo "  docker_image_prefix: $DOCKER_IMAGE_PREFIX"
echo "  container_repo_path: $CONTAINER_REPO_PATH"

# ---------------------------------------------------------------------------
# Build per-commit images
# ---------------------------------------------------------------------------
echo ""
echo "=== Reading commit SHAs from $COMMITS_FILE ==="

COMMIT_SHAS=$(jq -r '.commits[].sha' "$COMMITS_FILE")

for SHA in $COMMIT_SHAS; do
    # Skip placeholders
    if [[ "$SHA" == PLACEHOLDER* ]]; then
        echo "SKIP: $SHA looks like a placeholder -- replace it in configs/commits.json with a real SHA."
        continue
    fi

    SHORT_SHA="${SHA:0:7}"
    IMAGE_TAG="${DOCKER_IMAGE_PREFIX}:${SHORT_SHA}"

    echo ""
    echo "--- Building image $IMAGE_TAG (commit $SHA) ---"
    docker build \
        -f "$DOCKERFILE" \
        --build-arg "REPO_COMMIT=$SHA" \
        --build-arg "REPO_DIR=$REPO_NAME" \
        --build-arg "CONTAINER_REPO_PATH=$CONTAINER_REPO_PATH" \
        -t "$IMAGE_TAG" \
        "$PROJECT_ROOT"
    echo "--- Done: $IMAGE_TAG ---"
done

# ---------------------------------------------------------------------------
# Build HEAD / latest image
# ---------------------------------------------------------------------------
echo ""
echo "=== Building ${DOCKER_IMAGE_PREFIX}:latest (HEAD) ==="
docker build \
    -f "$DOCKERFILE" \
    --build-arg "REPO_COMMIT=HEAD" \
    --build-arg "REPO_DIR=$REPO_NAME" \
    --build-arg "CONTAINER_REPO_PATH=$CONTAINER_REPO_PATH" \
    -t "${DOCKER_IMAGE_PREFIX}:latest" \
    "$PROJECT_ROOT"
echo "=== Done: ${DOCKER_IMAGE_PREFIX}:latest ==="

echo ""
echo "All images built successfully."
docker images --filter "reference=${DOCKER_IMAGE_PREFIX}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
