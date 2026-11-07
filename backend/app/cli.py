import argparse
import asyncio
import json

from app.services.analysis import PullRequestAnalysisService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyse a GitHub pull request and print recommended tests."
    )
    parser.add_argument("pull_request_url")
    parser.add_argument(
        "--node-ids",
        action="store_true",
        help="Print only selected test identifiers for CI execution.",
    )
    args = parser.parse_args()
    result = asyncio.run(
        PullRequestAnalysisService().analyse(args.pull_request_url)
    )

    if args.node_ids:
        for test in result.recommended_tests:
            print(test.node_id)
    else:
        print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
