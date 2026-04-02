#!/bin/bash
# =============================================================================
# SERA Full SFT on Nemotron-3-Nano-30B-A3B
#
# SLURM job script for 2-node, 16-GPU full parameter fine-tuning.
# Full SFT requires more memory than LoRA — 2 nodes recommended.
#
# Usage:
#   sbatch training/slurm_sera_sft.sh
# =============================================================================

#SBATCH --job-name=sera-sft
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-node=8
#SBATCH --time=12:00:00
#SBATCH --partition=gpu
#SBATCH --output=logs/sera_sft_%j.out
#SBATCH --error=logs/sera_sft_%j.err
#SBATCH --exclusive

# ==============================================================================
# Configuration
# ==============================================================================

WORKSPACE=${WORKSPACE:-/workspace}
REPO_DIR=${REPO_DIR:-$WORKSPACE/repo-agents}
MEGATRON_BRIDGE_DIR=${MEGATRON_BRIDGE_DIR:-$WORKSPACE/Megatron-Bridge}
PRETRAINED_CHECKPOINT=${WORKSPACE}/models/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16
SEQ_LENGTH=4096

CONTAINER_IMAGE="${CONTAINER_IMAGE:-}"

# ==============================================================================
# Environment
# ==============================================================================

export TORCH_NCCL_AVOID_RECORD_STREAMS=1
export NCCL_NVLS_ENABLE=0

mkdir -p logs

echo "======================================"
echo "SERA Full SFT"
echo "======================================"
echo "Job ID: $SLURM_JOB_ID"
echo "Nodes: $SLURM_JOB_NUM_NODES"
echo "GPUs/node: $SLURM_GPUS_PER_NODE"
echo "======================================"

# ==============================================================================
# Launch — full SFT uses lower LR
# ==============================================================================

cd "$MEGATRON_BRIDGE_DIR"

CMD="torchrun --nproc_per_node=8 \
    $REPO_DIR/training/train_sera.py \
    --seq-length $SEQ_LENGTH \
    --data-dir $REPO_DIR/data/megatron_sft \
    --config-file $REPO_DIR/training/sera_overrides.yaml \
    checkpoint.pretrained_checkpoint=$PRETRAINED_CHECKPOINT \
    checkpoint.save=$WORKSPACE/results/sera_sft \
    optimizer.lr=5e-6 \
    model.tensor_model_parallel_size=2 \
    model.expert_model_parallel_size=8 \
    model.sequence_parallel=True \
    logger.wandb_exp_name=sera_oai5g_sft_$SLURM_JOB_ID"

if [ -n "$CONTAINER_IMAGE" ]; then
    srun --mpi=pmix --container-image="$CONTAINER_IMAGE" bash -c "$CMD"
else
    eval $CMD
fi

echo "======================================"
echo "Training complete"
echo "======================================"
