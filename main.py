#!/usr/bin/env python3

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict, Union

from dotenv import load_dotenv
from strip_ansi import strip_ansi
from supabase import Client, create_client

# Load environment variables
load_dotenv()

# Initialize Supabase client with anon key
supabase_url = os.getenv("SUPABASE_URL")
supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_anon_key)

patchwork_exec = os.getenv("PATCHWORK_EXEC")

output_dir = os.getenv("OUTPUT_DIR")

read_only = os.getenv("READ_ONLY", "false").lower() == "true"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
log.handlers = [handler]


class Patchflow(TypedDict):
    id: int
    name: str
    description: Optional[str]
    created_at: str
    graph: Dict[str, Any]
    is_published: bool
    is_verified: bool
    meta: Dict[str, Any]
    organization_id: Optional[int]


class PatchflowRun(TypedDict):
    created_at: str
    custom_patchflow_id: Union[int, None]
    id: int
    inputs: Dict[str, Any]
    meta: Dict[str, Any]
    organization_id: int
    outputs: Dict[str, Any]
    repository_id: int
    status: str
    patchflow: Patchflow


def save_run(run: PatchflowRun, only: Optional[List[str]] = None):
    update_data = {}
    if only is None:
        only = run.keys()
    for key in only:
        update_data[key] = run[key]
    if read_only:
        log.info(f"Would update run {run['id']} with {update_data}")
        return
    supabase.table("custom_patchflow_runs").update(update_data).eq("id", run["id"]).execute()


def authenticate_user():
    """Authenticate with username and password"""
    try:
        auth_response = supabase.auth.sign_in_with_password(
            {"email": os.getenv("SUPABASE_USER_EMAIL"), "password": os.getenv("SUPABASE_USER_PASSWORD")}
        )
        return auth_response
    except Exception as e:
        log.error(f"Authentication failed: {str(e)}")
        raise


def get_logger(run: PatchflowRun):
    new_logger = logging.getLogger(f"run[{run['id']}]")
    new_logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Clear existing handlers to prevent duplicate logging
    new_logger.handlers = []

    # Add the handler to the logger
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    new_logger.addHandler(handler)

    # Prevent propagation to root logger to avoid duplicate logs
    new_logger.propagate = False

    return new_logger


async def run_patchflow(run: PatchflowRun):
    logger = get_logger(run)
    logger.info(f"Running patchflow for run {run['id']}")
    output_path = os.path.join(output_dir, f"{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}_run_{run['id']}.json")

    try:
        args = [f"{key}={run['inputs'][key]}" for key in run["inputs"].keys()]
        cmd = [
            patchwork_exec,
            "Test",
            # run["patchflow"]["graph"]["name"],
            "--log",
            "debug",
            "--output",
            output_path,
            "--disable_telemetry",
            "--plain",
            *args,
        ]
        logger.info(f"Running command: {' '.join(cmd)}")
        promise = asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        run["status"] = "running"
        save_run(run, ["status"])
        process = await promise
        stdout, stderr = await process.communicate()
        logger.info("--- stdout ---")
        logger.info(strip_ansi(stdout.decode("utf-8")))
        logger.info("--- stderr ---")
        logger.error(strip_ansi(stderr.decode("utf-8")))
        logger.info("--- end ---")
        if process.returncode != 0:
            logger.error(f"Error running patchflow for run {run['id']}")
            run["status"] = "failed"
            save_run(run, ["status"])
        else:
            logger.info(f"Successfully ran patchflow for run {run['id']}")
            run["status"] = "pr_created"
            save_run(run, ["status"])

        try:
            with open(output_path, "r") as f:
                run["outputs"] = json.load(f)
                save_run(run, ["outputs"])
        except Exception:
            logger.info(f"No outputs found for run {run['id']}")

    except Exception as e:
        logger.error(f"Error running patchflow for run {run['id']}: {e}")
        run["status"] = "failed"
        save_run(run, ["status"])
        return


async def check_and_run_pending():
    try:
        os.makedirs(output_dir, exist_ok=True)

        # Authenticate user first
        authenticate_user()

        # Query for pending runs with is_private=true
        response = (
            supabase.table("custom_patchflow_runs")
            .select("*, patchflow:custom_patchflows(*)")
            .filter("status", "eq", "pending")
            .filter("meta->is_private", "eq", "true")
            .limit(10)
            .execute()
        )

        if len(response.data) == 0:
            log.info("No pending runs found")
            return

        runs = [PatchflowRun(datum) for datum in response.data]

        promises: List[asyncio.Task] = []
        # Process each pending run
        for run in runs:
            log.info(f"Triggering patchflow for run {run['id']}")

            # Run patchflow command
            log.info(f"Successfully triggered patchflow for run {run['id']}")
            promises.append(run_patchflow(run))

        await asyncio.gather(*promises)

    except Exception as e:
        log.error(f"Error checking pending runs: {str(e)}")


async def main_loop():
    while True:
        try:
            await check_and_run_pending()
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            log.info("Main loop cancelled")
            break


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        main_task = loop.create_task(main_loop())
        loop.run_until_complete(main_task)
    except KeyboardInterrupt:
        log.info("Service stopped by user")
        if main_task and not main_task.done():
            main_task.cancel()
            # Wait for the task to be cancelled
            try:
                loop.run_until_complete(main_task)
            except asyncio.CancelledError:
                pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
