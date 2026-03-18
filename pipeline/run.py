#!/usr/bin/env python3
"""Main discovery pipeline entry point.
Called by GitHub Actions with: python pipeline/run.py --source <name> --output-dir data/raw
Or for the full pipeline: python pipeline/run.py --pipeline
"""
import argparse
import json
import sys
from pathlib import Path


def run_scraper(source: str, output_dir: str) -> None:
    """Run a single scraper and write {source}.json."""
    from scrapers.github_trending import GitHubTrendingScraper
    from scrapers.hackernews import HackerNewsScraper
    from scrapers.reddit import RedditScraper
    from scrapers.lobsters import LobstersScraper
    from scrapers.github_search import GitHubSearchScraper
    from scrapers.huggingface import HuggingFaceScraper
    from scrapers.awesome_lists import AwesomeListsScraper

    scrapers = {
        "github_trending": GitHubTrendingScraper,
        "hackernews": HackerNewsScraper,
        "reddit": RedditScraper,
        "lobsters": LobstersScraper,
        "github_search": GitHubSearchScraper,
        "huggingface": HuggingFaceScraper,
        "awesome_lists": AwesomeListsScraper,
    }
    if source not in scrapers:
        print(f"Unknown source: {source}", file=sys.stderr)
        sys.exit(1)

    print(f"Scraping {source}...")
    repos = scrapers[source]().scrape()
    print(f"  Found {len(repos)} repos")

    out_path = Path(output_dir) / f"{source}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps([r.model_dump(mode="json") for r in repos], indent=2))
    print(f"  Written to {out_path}")


def run_pipeline(raw_dir: str = "data/raw") -> None:
    """Filter, deduplicate, score, and publish."""
    from schemas.repo import Repo
    from pipeline.filter import filter_repos
    from pipeline.deduplicate import deduplicate, load_seen_ids, save_seen_ids
    from pipeline.score import score_and_rank
    from pipeline.publish import write_spotlight_json
    from pages.build import build_index_html

    # Load all raw scraper outputs
    all_repos: list[Repo] = []
    for path in Path(raw_dir).glob("*.json"):
        try:
            data = json.loads(path.read_text())
            all_repos.extend([Repo(**r) for r in data])
        except Exception as e:
            print(f"  Warning: could not load {path}: {e}", file=sys.stderr)

    print(f"Total raw repos: {len(all_repos)}")

    # Merge repos appearing in multiple sources (track source_count for scoring)
    merged: dict[str, Repo] = {}
    for repo in all_repos:
        if repo.url not in merged:
            merged[repo.url] = repo
        else:
            # Increment source_count; keep higher stars_delta
            existing = merged[repo.url]
            merged[repo.url] = existing.model_copy(update={
                "source_count": existing.source_count + 1,
                "stars_delta": max(existing.stars_delta, repo.stars_delta),
            })
    unique_repos = list(merged.values())
    print(f"Unique repos: {len(unique_repos)}")

    # Filter
    filtered = filter_repos(unique_repos)
    print(f"After filter: {len(filtered)}")

    # Deduplicate against cache
    seen_ids = load_seen_ids()
    new_repos = deduplicate(filtered, seen_ids=seen_ids)
    print(f"New repos (not seen before): {len(new_repos)}")

    # Score and rank
    top_repos = score_and_rank(new_repos, top_n=5)
    print(f"Top repos: {len(top_repos)}")

    # Publish spotlight.json
    write_spotlight_json(top_repos)
    print("Written data/spotlight.json")

    # Update cache with all filtered repos (not just top 5)
    save_seen_ids(filtered, seen_ids)
    print("Cache updated")

    # Build GitHub Pages
    all_discovered_path = Path("data/all-discovered.json")
    all_discovered: list[Repo] = []
    if all_discovered_path.exists():
        try:
            all_discovered = [Repo(**r) for r in json.loads(all_discovered_path.read_text())]
        except Exception:
            pass
    all_discovered = list({r.url: r for r in (all_discovered + top_repos)}.values())
    all_discovered_path.write_text(json.dumps([r.model_dump(mode="json") for r in all_discovered], indent=2))

    html = build_index_html(all_discovered)
    Path("data/index.html").write_text(html)
    print("Written data/index.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="Run a single scraper")
    parser.add_argument("--output-dir", default="data/raw")
    parser.add_argument("--pipeline", action="store_true", help="Run full pipeline")
    args = parser.parse_args()

    if args.source:
        run_scraper(args.source, args.output_dir)
    elif args.pipeline:
        run_pipeline()
    else:
        parser.print_help()
        sys.exit(1)
