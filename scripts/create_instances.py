#!/usr/bin/env python3
"""
Create SWE-agent instance YAML files from extracted functions + bug prompts.

Generates stage_one_instances.yaml for use with `sweagent run-batch`.
"""

import json
import random
import sys
import yaml
from pathlib import Path


def load_repo_config(config_path: Path) -> dict:
    """Load repo_config.json if it exists."""
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-config", type=Path, default=Path("configs/repo_config.json"))
    parser.add_argument("--functions", type=Path, required=True)
    parser.add_argument("--bug-prompts", type=Path, required=True)
    parser.add_argument("--commits", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--num-samples", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    repo_cfg = load_repo_config(args.repo_config)
    docker_prefix = repo_cfg.get("docker_image_prefix", "sera")
    short_name = repo_cfg.get("repo_short_name", "repo")

    random.seed(args.seed)

    # Load data
    functions = []
    with open(args.functions) as f:
        for line in f:
            if line.strip():
                functions.append(json.loads(line))

    with open(args.bug_prompts) as f:
        bug_prompts = json.load(f)

    with open(args.commits) as f:
        commits_data = json.load(f)
    commits = [c["sha"] for c in commits_data["commits"]]

    print(f"Loaded {len(functions)} functions, {len(bug_prompts)} bugs, {len(commits)} commits")

    # Generate instances
    instances = []
    for i in range(args.num_samples):
        func = random.choice(functions)
        bug = random.choice(bug_prompts)
        commit = random.choice(commits)
        short_sha = commit[:7]
        image_name = f"{docker_prefix}:{short_sha}"

        instance = {
            "id": f"{short_name}_{short_sha}_{i:05d}",
            "image_name": image_name,
            "problem_statement": "n/a",  # Stage 1 uses template variables instead
            "repo_name": "repo",
            "extra_fields": {
                "start_fn": func["name"],
                "start_fn_file": func["file"],
                "bug_description": bug["description"],
                "bug_id": bug["bug_id"],
                "subsystem": func["subsystem"],
                "repo_display_name": repo_cfg.get("repo_display_name", "OpenAirInterface 5G"),
                "system_prompt_context": repo_cfg.get("system_prompt_context", ""),
                "build_caveat": repo_cfg.get("build_caveat", ""),
            },
        }
        instances.append(instance)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        yaml.safe_dump(instances, f, indent=2)

    print(f"Wrote {len(instances)} instances to {args.output}")


if __name__ == "__main__":
    main()
