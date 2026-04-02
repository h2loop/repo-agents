#!/bin/bash
# =============================================================================
# SERA LoRA Fine-Tuning on Nemotron-3-Nano-30B-A3B
#
# SLURM job script for 1-node, 8-GPU training with LoRA.
# Adjust #SBATCH directives and paths for your cluster.
#
# Usage:
#   sbatch training/slurm_sera_lora.sh
# =============================================================================

#SBATCH --job-name=sera-lora
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-node=8
#SBATCH --time=04:00:00
#SBATCH --partition=gpu
#SBATCH --output=logs/sera_lora_%j.out
#SBATCH --error=logs/sera_lora_%j.err
#SBATCH --exclusive

# ==============================================================================
# Configuration — adjust these for your cluster
# ==============================================================================

WORKSPACE=${WORKSPACE:-/workspace}
REPO_DIR=${REPO_DIR:-$WORKSPACE/repo-agents}
MEGATRON_BRIDGE_DIR=${MEGATRON_BRIDGE_DIR:-$WORKSPACE/Megatron-Bridge}
PRETRAINED_CHECKPOINT=${WORKSPACE}/models/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16
SEQ_LENGTH=4096

# Container (if using enroot/pyxis)
CONTAINER_IMAGE="${CONTAINER_IMAGE:-}"

# ==============================================================================
# Environment
# ==============================================================================

export TORCH_NCCL_AVOID_RECORD_STREAMS=1
export NCCL_NVLS_ENABLE=0

# Uncomment for shared filesystem caches
# export UV_CACHE_DIR="$WORKSPACE/.uv_cache"
# export HF_HOME="$WORKSPACE/.hf_cache"
# export HF_TOKEN="hf_..."
# export WANDB_API_KEY="..."

mkdir -p logs

echo "======================================"
echo "SERA LoRA Fine-Tuning"
echo "======================================"
echo "Job ID: $SLURM_JOB_ID"
echo "Nodes: $SLURM_JOB_NUM_NODES"
echo "GPUs/node: $SLURM_GPUS_PER_NODE"
echo "Pretrained: $PRETRAINED_CHECKPOINT"
echo "Data: $REPO_DIR/data/megatron_sft/"
echo "Seq length: $SEQ_LENGTH"
echo "======================================"

# ==============================================================================
# Launch
# ==============================================================================

cd "$MEGATRON_BRIDGE_DIR"

CMD="torchrun --nproc_per_node=8 \
    $REPO_DIR/training/train_sera.py \
    --peft lora \
    --seq-length $SEQ_LENGTH \
    --data-dir $REPO_DIR/data/megatron_sft \
    --config-file $REPO_DIR/training/sera_overrides.yaml \
    checkpoint.pretrained_checkpoint=$PRETRAINED_CHECKPOINT \
    checkpoint.save=$WORKSPACE/results/sera_lora \
    logger.wandb_exp_name=sera_oai5g_lora_$SLURM_JOB_ID"

if [ -n "$CONTAINER_IMAGE" ]; then
    srun --mpi=pmix --container-image="$CONTAINER_IMAGE" bash -c "$CMD"
else
    eval $CMD
fi

echo "======================================"
echo "Training complete"
echo "======================================"
