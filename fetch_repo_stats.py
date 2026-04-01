import csv
import json
import time
import urllib.request
import urllib.error
import ssl
import sys

# Bypass SSL certificate verification (macOS Python issue)
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

TOKEN = "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"
GRAPHQL_URL = "https://api.github.com/graphql"

# Extract unique repo URLs
repos = set()
with open("Generic_scraped.csv", "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        url = row["repo_url"].strip()
        if "github.com" in url:
            repos.add(url)

repos = sorted(repos)
print(f"Total unique repos: {len(repos)}", file=sys.stderr)

# Parse owner/repo from URLs
parsed = []
for url in repos:
    parts = url.rstrip("/").split("/")
    if len(parts) >= 5:
        owner, name = parts[3], parts[4]
        parsed.append((owner, name, url))

# Batch GraphQL queries (25 repos per batch)
BATCH_SIZE = 25
results = []

def make_graphql_query(batch):
    """Build a GraphQL query for a batch of repos."""
    parts = []
    for i, (owner, name, url) in enumerate(batch):
        alias = f"repo_{i}"
        parts.append(f'''
        {alias}: repository(owner: "{owner}", name: "{name}") {{
            nameWithOwner
            stargazerCount
            forkCount
            issues(states: [OPEN]) {{ totalCount }}
            openPRs: pullRequests(states: [OPEN]) {{ totalCount }}
            closedPRs: pullRequests(states: [CLOSED]) {{ totalCount }}
            mergedPRs: pullRequests(states: [MERGED]) {{ totalCount }}
        }}''')
    return "query {" + "\n".join(parts) + "\n}"

def fetch_batch(batch, batch_num, total_batches):
    query = make_graphql_query(batch)
    data = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(GRAPHQL_URL, data=data, method="POST")
    req.add_header("Authorization", f"bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  HTTP error {e.code} on batch {batch_num}", file=sys.stderr)
        if e.code == 403:
            print("  Rate limited, waiting 60s...", file=sys.stderr)
            time.sleep(60)
            return fetch_batch(batch, batch_num, total_batches)
        return []
    except Exception as e:
        print(f"  Error on batch {batch_num}: {e}", file=sys.stderr)
        return []

    batch_results = []
    if "data" in body:
        for i, (owner, name, url) in enumerate(batch):
            alias = f"repo_{i}"
            repo_data = body["data"].get(alias)
            if repo_data:
                closed_prs = repo_data["closedPRs"]["totalCount"]
                merged_prs = repo_data["mergedPRs"]["totalCount"]
                batch_results.append({
                    "repo": repo_data["nameWithOwner"],
                    "url": url,
                    "stars": repo_data["stargazerCount"],
                    "forks": repo_data["forkCount"],
                    "open_issues": repo_data["issues"]["totalCount"],
                    "open_prs": repo_data["openPRs"]["totalCount"],
                    "closed_prs": closed_prs,
                    "merged_prs": merged_prs,
                    "total_closed_prs": closed_prs + merged_prs,
                })
            else:
                batch_results.append({
                    "repo": f"{owner}/{name}",
                    "url": url,
                    "stars": None,
                    "forks": None,
                    "open_issues": None,
                    "open_prs": None,
                    "closed_prs": None,
                    "merged_prs": None,
                    "total_closed_prs": None,
                })
    if "errors" in body:
        for err in body["errors"]:
            print(f"  GraphQL error: {err.get('message', err)}", file=sys.stderr)

    return batch_results

total_batches = (len(parsed) + BATCH_SIZE - 1) // BATCH_SIZE
for batch_num in range(total_batches):
    start = batch_num * BATCH_SIZE
    end = start + BATCH_SIZE
    batch = parsed[start:end]
    print(f"Fetching batch {batch_num+1}/{total_batches} ({len(batch)} repos)...", file=sys.stderr)
    batch_results = fetch_batch(batch, batch_num+1, total_batches)
    results.extend(batch_results)
    time.sleep(0.5)  # small delay between batches

# Write results to CSV
output_file = "repo_stats.csv"
with open(output_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["repo", "url", "stars", "forks", "open_issues", "open_prs", "closed_prs", "merged_prs", "total_closed_prs"])
    for r in results:
        writer.writerow([r["repo"], r["url"], r["stars"], r["forks"], r["open_issues"], r["open_prs"], r["closed_prs"], r["merged_prs"], r["total_closed_prs"]])

print(f"\nResults written to {output_file}", file=sys.stderr)
print(f"Successfully fetched: {sum(1 for r in results if r['stars'] is not None)}/{len(results)}", file=sys.stderr)

# Print sorted tables
valid = [r for r in results if r["stars"] is not None]

print("\n\n=== TOP REPOS BY STARS ===")
for i, r in enumerate(sorted(valid, key=lambda x: x["stars"], reverse=True)[:50], 1):
    print(f"{i:3}. {r['repo']:50s}  Stars: {r['stars']:>8,}")

print("\n\n=== TOP REPOS BY FORKS ===")
for i, r in enumerate(sorted(valid, key=lambda x: x["forks"], reverse=True)[:50], 1):
    print(f"{i:3}. {r['repo']:50s}  Forks: {r['forks']:>8,}")

print("\n\n=== TOP REPOS BY OPEN ISSUES ===")
for i, r in enumerate(sorted(valid, key=lambda x: x["open_issues"], reverse=True)[:50], 1):
    print(f"{i:3}. {r['repo']:50s}  Issues: {r['open_issues']:>8,}")

print("\n\n=== TOP REPOS BY OPEN PRs ===")
for i, r in enumerate(sorted(valid, key=lambda x: x["open_prs"], reverse=True)[:50], 1):
    print(f"{i:3}. {r['repo']:50s}  PRs: {r['open_prs']:>8,}")

print("\n\n=== TOP REPOS BY CLOSED PRs (closed without merge) ===")
for i, r in enumerate(sorted(valid, key=lambda x: x["closed_prs"], reverse=True)[:50], 1):
    print(f"{i:3}. {r['repo']:50s}  Closed PRs: {r['closed_prs']:>8,}")

print("\n\n=== TOP REPOS BY MERGED PRs ===")
for i, r in enumerate(sorted(valid, key=lambda x: x["merged_prs"], reverse=True)[:50], 1):
    print(f"{i:3}. {r['repo']:50s}  Merged PRs: {r['merged_prs']:>8,}")

print("\n\n=== TOP REPOS BY TOTAL CLOSED PRs (closed + merged) ===")
for i, r in enumerate(sorted(valid, key=lambda x: x["total_closed_prs"], reverse=True)[:50], 1):
    print(f"{i:3}. {r['repo']:50s}  Total Closed: {r['total_closed_prs']:>8,}")
