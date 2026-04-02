#!/usr/bin/env python3
"""
Populate configs/repo_config.json for a new target repository.

Gathers deterministic signals from the repo (directory structure, file types,
README, build system) and uses the teacher LLM for semantic fields (description,
subsystem mapping, demo PR, etc.).

Usage:
    python scripts/populate_repo_config.py \
        --repo-path /path/to/cloned/repo \
        --output configs/repo_config.json

    # Dry run — print to stdout, don't write
    python scripts/populate_repo_config.py \
        --repo-path /path/to/cloned/repo \
        --dry-run

Environment variables:
    LLM_BASE_URL  - LiteLLM proxy URL (default: https://litellm-prod-909645453767.asia-south1.run.app)
    LLM_API_KEY   - API key (default: sk-1234)
    LLM_MODEL     - Model ID (default: qwen/qwen3-coder-480b-a35b-instruct-maas)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# LLM configuration
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("LLM_BASE_URL", "https://litellm-prod-909645453767.asia-south1.run.app")
API_KEY = os.getenv("LLM_API_KEY", "sk-1234")
MODEL = os.getenv("LLM_MODEL", "qwen/qwen3-coder-480b-a35b-instruct-maas")

# C/C++ file extensions
C_CPP_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}

# Directories to skip when scanning
SKIP_DIRS = {
    ".git", ".svn", ".hg", "build", "Build", "cmake-build-debug",
    "cmake-build-release", "__pycache__", "node_modules", ".venv",
    "venv", "third_party", "3rdparty", "external", "vendor",
}


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

def chat_completion(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    """Call the LLM via the OpenAI-compatible proxy. Returns content string."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=300,
    )
    resp.raise_for_status()
    msg = resp.json()["choices"][0]["message"]
    return (msg.get("content") or msg.get("reasoning_content") or "").strip()


def parse_json_response(text: str) -> dict | list:
    """Extract JSON object or array from LLM response, handling markdown fences."""
    # Strip markdown code fences
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting the first JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM response:\n{text[:500]}")


# ---------------------------------------------------------------------------
# Repo snapshot gathering
# ---------------------------------------------------------------------------

def gather_repo_snapshot(repo_path: Path) -> dict:
    """Collect deterministic signals from the repository."""
    snapshot: dict = {}

    # Basic identity
    snapshot["repo_name"] = repo_path.name

    # Git remote
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, cwd=repo_path, timeout=10,
        )
        snapshot["git_remote"] = result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        snapshot["git_remote"] = ""

    # README
    readme_text = ""
    for name in ["README.md", "README.rst", "README.txt", "README"]:
        readme_path = repo_path / name
        if readme_path.is_file():
            try:
                readme_text = readme_path.read_text(errors="replace")[:3000]
            except Exception:
                pass
            break
    snapshot["readme_text"] = readme_text

    # Top-level directories (excluding skips)
    top_dirs = sorted([
        d.name for d in repo_path.iterdir()
        if d.is_dir() and d.name not in SKIP_DIRS and not d.name.startswith(".")
    ])
    snapshot["top_dirs"] = top_dirs

    # Directory tree (depth 2)
    tree_lines = []
    for d in top_dirs[:30]:  # cap at 30 dirs
        tree_lines.append(f"{d}/")
        subdir = repo_path / d
        if subdir.is_dir():
            subdirs = sorted([
                sd.name for sd in subdir.iterdir()
                if sd.is_dir() and sd.name not in SKIP_DIRS and not sd.name.startswith(".")
            ])
            for sd in subdirs[:15]:  # cap per dir
                tree_lines.append(f"  {d}/{sd}/")
    snapshot["tree_output"] = "\n".join(tree_lines)

    # File extension distribution
    ext_counter: Counter = Counter()
    for root, dirs, files in os.walk(repo_path):
        # Prune skip dirs
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            ext = Path(f).suffix.lower()
            if ext:
                ext_counter[ext] += 1
    # Top 20 extensions
    snapshot["ext_distribution"] = dict(ext_counter.most_common(20))

    # Source file counts per top-level dir
    dir_file_counts = {}
    for d in top_dirs:
        count = 0
        dpath = repo_path / d
        if dpath.is_dir():
            for root, dirs, files in os.walk(dpath):
                dirs[:] = [dd for dd in dirs if dd not in SKIP_DIRS]
                count += sum(1 for f in files if Path(f).suffix.lower() in C_CPP_EXTENSIONS)
        if count > 0:
            dir_file_counts[d] = count
    snapshot["dir_c_cpp_counts"] = dir_file_counts

    # Build system detection
    build_files = []
    for name in ["CMakeLists.txt", "Makefile", "configure", "configure.ac",
                  "meson.build", "SConstruct", "BUILD", "WORKSPACE"]:
        if (repo_path / name).exists():
            build_files.append(name)
    snapshot["build_files"] = build_files

    # Dockerfile presence
    has_dockerfile = (repo_path / "Dockerfile").exists() or (repo_path / "docker").is_dir()
    snapshot["has_dockerfile"] = has_dockerfile

    # Top-level file listing
    top_files = sorted([
        f.name for f in repo_path.iterdir()
        if f.is_file() and not f.name.startswith(".")
    ])[:30]
    snapshot["top_files"] = top_files

    return snapshot


def find_scan_dirs(repo_path: Path, top_dirs: list[str]) -> list[str]:
    """Find top-level directories containing C/C++ source files."""
    scan_dirs = []
    for d in top_dirs:
        dpath = repo_path / d
        if not dpath.is_dir():
            continue
        has_c_cpp = False
        for root, dirs, files in os.walk(dpath):
            dirs[:] = [dd for dd in dirs if dd not in SKIP_DIRS]
            if any(Path(f).suffix.lower() in C_CPP_EXTENSIONS for f in files):
                has_c_cpp = True
                break
        if has_c_cpp:
            scan_dirs.append(d)
    return scan_dirs


# ---------------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------------

IDENTITY_PROMPT = """\
You are a software project analyst. Given information about a C/C++ git repository, \
produce a structured JSON configuration. Be concise and accurate.

## Repository snapshot
- Directory name: {repo_name}
- Git remote: {git_remote}

### README (first 3000 chars):
{readme_text}

### Top-level directories:
{top_dirs}

### Directory tree (depth 2):
{tree_output}

### C/C++ source file counts by top-level directory:
{dir_c_cpp_counts}

### File extension distribution (top 20):
{ext_distribution}

### Build system files found at repo root:
{build_files}

### Has Dockerfile: {has_dockerfile}

## Required output
Return a JSON object with exactly these keys:
{{
  "repo_short_name": "<2-6 char lowercase alphanumeric abbreviation suitable for file prefixes and docker tags>",
  "repo_display_name": "<human-readable project name, title case>",
  "repo_description": "<one-line description starting with a lowercase letter, suitable for completing 'The codebase is ...'>",
  "system_prompt_context": "<1-3 sentence paragraph describing what the repo implements, its primary language, and build system. Plain text, no markup.>",
  "subsystem_description": "<compact mapping of the C/C++ source directories to what they contain, like 'core engine (src/core), networking (src/net), utils (src/util)'. Reference actual directory names.>",
  "build_caveat": "<one-sentence warning about what might not work in a minimal Docker container with only gcc/cmake/make installed, or empty string if standard builds should work fine>"
}}

Rules:
- repo_short_name must match [a-z][a-z0-9]{{1,5}} (no hyphens, no underscores)
- repo_description should be a noun phrase, not a full sentence
- system_prompt_context should mention the specific domain/purpose, primary language (C, C++, or mix), and build tooling
- subsystem_description should only cover directories that actually contain C/C++ source code
- build_caveat should mention specific reasons (hardware SDKs, proprietary deps, etc). Use empty string "" if a standard cmake/make build should work fine in a container
- Return ONLY the JSON object, no other text
"""

DEMO_PR_PROMPT = """\
You are an expert C/C++ developer familiar with the {repo_display_name} project.

Repository context:
- Description: {repo_description}
- What it does: {system_prompt_context}
- Subsystems: {subsystem_description}
- Source directories with C/C++ code: {scan_dirs}

Write a single realistic example pull request for this repository. The PR should describe \
a plausible C/C++ bug fix (buffer overflow, null pointer dereference, off-by-one, memory leak, \
race condition, or similar).

Use this exact format:
## Title: <short title>

### Summary
<2-3 paragraph summary describing the bug and the fix>

### Changes
- `<file_path>`: <what changed>
- `<file_path>`: <what changed>

### Testing
- <how it was tested>

Rules:
- File paths must use actual directory names from the source directories listed above
- The bug should be realistic for this specific codebase and domain
- Keep it to 1-3 file changes
- Do NOT wrap the output in code fences — return the markdown directly
"""


def generate_identity_fields(snapshot: dict) -> dict:
    """Call 1: Generate semantic identity fields via LLM."""
    prompt = IDENTITY_PROMPT.format(
        repo_name=snapshot["repo_name"],
        git_remote=snapshot["git_remote"],
        readme_text=snapshot["readme_text"] or "(no README found)",
        top_dirs=", ".join(snapshot["top_dirs"]),
        tree_output=snapshot["tree_output"],
        dir_c_cpp_counts=json.dumps(snapshot["dir_c_cpp_counts"], indent=2),
        ext_distribution=json.dumps(snapshot["ext_distribution"], indent=2),
        build_files=", ".join(snapshot["build_files"]) or "(none found)",
        has_dockerfile=snapshot["has_dockerfile"],
    )

    messages = [{"role": "user", "content": prompt}]
    print("  Calling LLM for identity fields...", file=sys.stderr)
    response = chat_completion(messages, temperature=0.3, max_tokens=2048)
    return parse_json_response(response)


def collect_source_subdirs(repo_path: Path, scan_dirs: list[str]) -> dict[str, int]:
    """Collect C/C++ source subdirectories (depth 2) with file counts."""
    subdir_counts: dict[str, int] = {}
    for sd in scan_dirs:
        sd_path = repo_path / sd
        if not sd_path.is_dir():
            continue
        for root, dirs, files in os.walk(sd_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            rel = os.path.relpath(root, repo_path)
            depth = rel.count(os.sep)
            if depth > 2:
                dirs.clear()
                continue
            c_count = sum(1 for f in files if Path(f).suffix.lower() in C_CPP_EXTENSIONS)
            if c_count > 0:
                subdir_counts[rel] = c_count
    return subdir_counts


# The canonical subsystem names used in bug_prompts.json (from OAI5G).
# The LLM will map these to actual directories in the target repo.
CANONICAL_SUBSYSTEMS = [
    "openair1/PHY",
    "openair2/LAYER2/MAC",
    "openair2/LAYER2/RLC",
    "openair2/LAYER2/PDCP",
    "openair2/RRC",
    "openair2/NAS",
    "openair3/NAS",
    "openair3/S1AP",
    "openair3/NGAP",
    "common",
    "executables",
    "radio",
    "nfapi",
]

SUBSYSTEM_MAP_PROMPT = """\
You are a 5G/telecom software analyst. Given two repositories — a source repo (OpenAirInterface 5G) and a target repo — produce a mapping from the source repo's subsystem directory paths to equivalent directories in the target repo.

## Source repo subsystem paths (OpenAirInterface 5G):
{canonical_subsystems}

## Target repo: {repo_display_name}
- Description: {system_prompt_context}

### Target repo directories with C/C++ source file counts:
{subdir_counts}

## Task
Return a JSON object mapping each source subsystem path to a list of equivalent target repo directory paths. If a source subsystem has no equivalent in the target repo, map it to an empty list.

Use the actual directory paths from the target repo listing above. Map based on functional equivalence:
- "openair1/PHY" → directories containing PHY layer code
- "openair2/LAYER2/MAC" → directories containing MAC layer / scheduler code
- "openair2/LAYER2/RLC" → directories containing RLC layer code
- "openair2/LAYER2/PDCP" → directories containing PDCP layer code
- "openair2/RRC" → directories containing RRC layer code
- "openair2/NAS", "openair3/NAS" → directories containing NAS layer code (if any)
- "openair3/S1AP" → directories containing S1AP or equivalent interface code (if any)
- "openair3/NGAP" → directories containing NGAP interface code
- "common" → directories containing common utilities, support libraries
- "executables" → directories containing application entry points
- "radio" → directories containing radio/RF/RU code
- "nfapi" → directories containing FAPI/nFAPI or similar north-bound interface code

Example output format:
{{
  "openair1/PHY": ["lib/phy"],
  "openair2/LAYER2/MAC": ["lib/mac", "lib/scheduler"],
  "common": ["lib/support", "lib/srslog"],
  "openair3/S1AP": [],
  ...
}}

Return ONLY the JSON object, no other text.
"""


def generate_subsystem_mapping(
    identity: dict,
    subdir_counts: dict[str, int],
) -> dict[str, list[str]]:
    """Call 3: Generate subsystem mapping from canonical OAI5G paths to target repo paths."""
    counts_str = "\n".join(f"  {d}: {c} files" for d, c in sorted(subdir_counts.items()))

    prompt = SUBSYSTEM_MAP_PROMPT.format(
        canonical_subsystems="\n".join(f"  {s}" for s in CANONICAL_SUBSYSTEMS),
        repo_display_name=identity["repo_display_name"],
        system_prompt_context=identity["system_prompt_context"],
        subdir_counts=counts_str,
    )

    messages = [{"role": "user", "content": prompt}]
    print("  Calling LLM for subsystem mapping...", file=sys.stderr)
    response = chat_completion(messages, temperature=0.1, max_tokens=2048)
    return parse_json_response(response)


def remap_bug_prompts(
    source_prompts_path: Path,
    subsystem_map: dict[str, list[str]],
) -> list[dict]:
    """Apply subsystem mapping to the canonical bug_prompts.json."""
    with open(source_prompts_path) as f:
        prompts = json.load(f)

    remapped = []
    for bug in prompts:
        new_subsystems = []
        for old_sub in bug.get("subsystems", []):
            mapped = subsystem_map.get(old_sub, [])
            new_subsystems.extend(mapped)
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for s in new_subsystems:
            if s not in seen:
                seen.add(s)
                deduped.append(s)
        if deduped:  # Only keep bugs that have at least one mapped subsystem
            remapped.append({
                "bug_id": bug["bug_id"],
                "description": bug["description"],
                "domain": bug["domain"],
                "subsystems": deduped,
            })

    return remapped


def generate_fallback_pr(identity: dict, scan_dirs: list[str]) -> str:
    """Call 2: Generate a realistic demo PR via LLM."""
    prompt = DEMO_PR_PROMPT.format(
        repo_display_name=identity["repo_display_name"],
        repo_description=identity["repo_description"],
        system_prompt_context=identity["system_prompt_context"],
        subsystem_description=identity["subsystem_description"],
        scan_dirs=", ".join(scan_dirs),
    )

    messages = [{"role": "user", "content": prompt}]
    print("  Calling LLM for fallback demo PR...", file=sys.stderr)
    response = chat_completion(messages, temperature=0.7, max_tokens=2048)

    # Strip any accidental code fences
    response = re.sub(r"^```(?:markdown)?\s*\n?", "", response.strip())
    response = re.sub(r"\n?```\s*$", "", response.strip())
    return response.strip()


# ---------------------------------------------------------------------------
# Config assembly
# ---------------------------------------------------------------------------

def assemble_config(
    snapshot: dict,
    identity: dict,
    scan_dirs: list[str],
    fallback_pr: str,
    bug_prompts_file: str,
) -> dict:
    """Merge deterministic + LLM fields into final repo_config.json."""
    short_name = identity["repo_short_name"]

    return {
        "_comment_identity": "Identifies the target repo. repo_name is the local directory name.",
        "repo_name": snapshot["repo_name"],
        "repo_short_name": short_name,
        "repo_display_name": identity["repo_display_name"],

        "_comment_description": "Short description used in system prompts after 'The codebase is ...'",
        "repo_description": identity["repo_description"],

        "_comment_system_prompt_context": "Longer paragraph injected into agent system prompts describing what the repo contains, its language, build system, etc. Written as plain text (no markup).",
        "system_prompt_context": identity["system_prompt_context"],

        "_comment_scan_dirs": "Top-level directories to scan for function extraction.",
        "scan_dirs": scan_dirs,

        "_comment_subsystem_description": "Human-readable subsystem mapping used in training system prompts.",
        "subsystem_description": identity["subsystem_description"],

        "_comment_docker": "Docker image prefix and container-internal path where the repo is mounted.",
        "docker_image_prefix": f"{short_name}-sera",
        "container_repo_path": "/repo",

        "_comment_build_note": "Warning shown to agents about build limitations. Set to empty string if full builds work.",
        "build_caveat": identity.get("build_caveat", ""),

        "_comment_functions_file": "Path to the extracted functions JSONL, relative to project root.",
        "functions_file": f"data/{short_name}_functions.jsonl",

        "_comment_bug_prompts_file": "Path to the bug prompts JSON, relative to project root. Generated by populate_repo_config.py.",
        "bug_prompts_file": bug_prompts_file,

        "_comment_fallback_demo_pr": "Placeholder PR used when no demo_prs/ directory is found. Should be a realistic example from this repo.",
        "fallback_demo_pr": fallback_pr,
    }


def validate_config(config: dict) -> list[str]:
    """Validate the assembled config. Returns list of warnings."""
    warnings = []

    short = config.get("repo_short_name", "")
    if not re.match(r"^[a-z][a-z0-9]{1,5}$", short):
        warnings.append(f"repo_short_name '{short}' does not match [a-z][a-z0-9]{{1,5}}")

    if not config.get("scan_dirs"):
        warnings.append("scan_dirs is empty — no C/C++ source directories found")

    required = [
        "repo_name", "repo_short_name", "repo_display_name", "repo_description",
        "system_prompt_context", "subsystem_description", "docker_image_prefix",
        "container_repo_path", "functions_file", "fallback_demo_pr",
    ]
    for key in required:
        if not config.get(key):
            warnings.append(f"Missing or empty required field: {key}")

    return warnings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Populate repo_config.json for a new target repository"
    )
    parser.add_argument(
        "--repo-path", type=Path, required=True,
        help="Path to the cloned target repository",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("configs/repo_config.json"),
        help="Output path for repo_config.json (default: configs/repo_config.json)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print config to stdout instead of writing to file",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing config without prompting",
    )
    args = parser.parse_args()

    repo_path = args.repo_path.resolve()
    if not repo_path.is_dir():
        sys.exit(f"Error: repo path does not exist: {repo_path}")
    if not (repo_path / ".git").is_dir():
        print(f"Warning: {repo_path} is not a git repo", file=sys.stderr)

    # Check for existing config
    if not args.dry_run and args.output.exists() and not args.force:
        print(f"Error: {args.output} already exists. Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    # Step 1: Gather repo snapshot
    print("Gathering repo snapshot...", file=sys.stderr)
    snapshot = gather_repo_snapshot(repo_path)
    print(f"  Repo name:    {snapshot['repo_name']}", file=sys.stderr)
    print(f"  Git remote:   {snapshot['git_remote'] or '(none)'}", file=sys.stderr)
    print(f"  Top dirs:     {len(snapshot['top_dirs'])}", file=sys.stderr)
    print(f"  README:       {'found' if snapshot['readme_text'] else 'not found'} ({len(snapshot['readme_text'])} chars)", file=sys.stderr)
    print(f"  Build files:  {snapshot['build_files'] or '(none)'}", file=sys.stderr)
    print(f"  Extensions:   {dict(list(snapshot['ext_distribution'].items())[:5])}...", file=sys.stderr)

    # Step 2: Find scan directories
    scan_dirs = find_scan_dirs(repo_path, snapshot["top_dirs"])
    print(f"  Scan dirs:    {scan_dirs}", file=sys.stderr)
    if not scan_dirs:
        print("Warning: No directories with C/C++ source files found!", file=sys.stderr)

    # Step 3: LLM call 1 — identity fields
    print("\nGenerating identity fields...", file=sys.stderr)
    identity = generate_identity_fields(snapshot)
    print(f"  short_name:   {identity.get('repo_short_name')}", file=sys.stderr)
    print(f"  display_name: {identity.get('repo_display_name')}", file=sys.stderr)
    print(f"  description:  {identity.get('repo_description', '')[:80]}...", file=sys.stderr)

    # Step 4: LLM call 2 — fallback demo PR
    print("\nGenerating fallback demo PR...", file=sys.stderr)
    fallback_pr = generate_fallback_pr(identity, scan_dirs)
    pr_title = fallback_pr.split("\n")[0] if fallback_pr else "(empty)"
    print(f"  PR title:     {pr_title}", file=sys.stderr)

    # Step 5: LLM call 3 — subsystem mapping + bug prompts
    short_name = identity["repo_short_name"]
    bug_prompts_rel = f"configs/bug_prompts_{short_name}.json"
    source_bug_prompts = Path("configs/bug_prompts.json")

    if source_bug_prompts.exists():
        print("\nGenerating subsystem mapping for bug prompts...", file=sys.stderr)
        subdir_counts = collect_source_subdirs(repo_path, scan_dirs)
        print(f"  Source subdirectories: {len(subdir_counts)}", file=sys.stderr)

        subsystem_map = generate_subsystem_mapping(identity, subdir_counts)
        mapped_count = sum(1 for v in subsystem_map.values() if v)
        print(f"  Mapped {mapped_count}/{len(CANONICAL_SUBSYSTEMS)} canonical subsystems", file=sys.stderr)
        for src, tgt in sorted(subsystem_map.items()):
            if tgt:
                print(f"    {src} → {tgt}", file=sys.stderr)

        bug_prompts = remap_bug_prompts(source_bug_prompts, subsystem_map)
        print(f"  Bug prompts with mapped subsystems: {len(bug_prompts)}", file=sys.stderr)

        if not args.dry_run:
            bug_prompts_path = Path(bug_prompts_rel)
            bug_prompts_path.parent.mkdir(parents=True, exist_ok=True)
            with open(bug_prompts_path, "w") as f:
                json.dump(bug_prompts, f, indent=2)
                f.write("\n")
            print(f"  Written to {bug_prompts_path}", file=sys.stderr)
        else:
            print(f"\n  [dry-run] Would write {len(bug_prompts)} bug prompts to {bug_prompts_rel}", file=sys.stderr)
    else:
        print(f"\nWarning: {source_bug_prompts} not found, skipping bug prompt generation", file=sys.stderr)
        bug_prompts_rel = "configs/bug_prompts.json"

    # Step 6: Assemble config
    config = assemble_config(snapshot, identity, scan_dirs, fallback_pr, bug_prompts_rel)

    # Step 6: Validate
    warnings = validate_config(config)
    if warnings:
        print(f"\nValidation warnings:", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)

    # Step 7: Output
    config_json = json.dumps(config, indent=2, ensure_ascii=False)

    if args.dry_run:
        print(config_json)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            f.write(config_json + "\n")
        print(f"\nWritten to {args.output}", file=sys.stderr)

    print("\nDone.", file=sys.stderr)


if __name__ == "__main__":
    main()
