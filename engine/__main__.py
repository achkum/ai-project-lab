"""Run from the repository root: python -m engine doctor | dry-run."""
import argparse
import json
from pathlib import Path
from .queue import Queue
from .routing import resolve_model, SetupRequired

def main():
    parser = argparse.ArgumentParser(description="Lab foundation; no paid calls or remote execution")
    parser.add_argument("command",choices=["doctor","dry-run"])
    parser.add_argument("--runtime",default="runtime")
    args = parser.parse_args()
    if args.command == "doctor":
        policy = json.loads(Path("config/model-policy.example.json").read_text(encoding="utf-8"))
        try:
            route = resolve_model(policy,"initial_analysis")
            print(json.dumps({"state":"model_binding_present_not_verified","route":route}))
        except SetupRequired as exc:
            print(json.dumps({"state":"needs_setup","reason":str(exc),
                              "paid_calls_enabled":False,"scheduler_installed":False}))
    else:
        queue = Queue(Path(args.runtime)/"dry-run.sqlite")
        try:
            # Separate fixture namespace/database: never count this as research or a release.
            job_id = queue.enqueue("fixture:queue-smoke:v1","thesis","fixture_no_model",{"sample":True})
            job = queue.claim("local-smoke","thesis")
            if job:
                queue.heartbeat(job_id,job["token"])
                queue.finish(job_id,job["token"],{"fixture_only":True})
            print(json.dumps({"mode":"dry_run","queue":queue.summary(),
                              "research_runs":0,"product_releases":0,"model_calls":0}))
        finally:
            queue.close()

if __name__ == "__main__":
    main()

