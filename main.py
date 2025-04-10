#!/usr/bin/env python3

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from strip_ansi import strip_ansi

# Load environment variables
load_dotenv()

# Initialize Postgres connection parameters
db_host = os.getenv("DB_HOST")
db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_port = os.getenv("DB_PORT", "5432")
organization_id = os.getenv("ORGANIZATION_ID")

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
    name: str
    graph: Dict[str, Any]


class PatchflowRun(TypedDict):
    id: int
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    status: str
    patchflow: Patchflow


def get_db_connection():
    """Create and return a database connection"""
    try:
        conn = psycopg2.connect(host=db_host, database=db_name, user=db_user, password=db_password, port=db_port)
        return conn
    except Exception as e:
        log.error(f"Database connection failed: {str(e)}")
        raise


def save_run(run: PatchflowRun, only: Optional[List[str]] = None):
    if only is None:
        only = run.keys()

    update_fields = []
    update_values = []

    for key in only:
        if key in run and key != "patchflow":  # Skip the patchflow object
            update_fields.append(f"{key} = %s")
            update_values.append(json.dumps(run[key]) if isinstance(run[key], dict) else run[key])

    if not update_fields:
        return

    update_query = f"UPDATE custom_patchflow_runs SET {', '.join(update_fields)} WHERE id = %s"
    update_values.append(run["id"])

    if read_only:
        log.info(f"Would update run {run['id']} with {update_fields}, {update_values}")
        return

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(update_query, update_values)
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"Error updating run {run['id']}: {str(e)}")


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
            run["patchflow"]["graph"]["name"],
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

        # Get pending runs with is_private=true
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(f"""
                SELECT r.*, p.name as p_name, p.graph as p_graph
                FROM custom_patchflow_runs r
                LEFT JOIN custom_patchflows p ON r.custom_patchflow_id = p.id
                WHERE r.status = 'pending'
                AND r.organization_id = {organization_id}
                AND r.meta->>'is_private' = 'true'
                LIMIT 10
            """)
            data = cursor.fetchall()
        conn.close()

        if len(data) == 0:
            log.info("No pending runs found")
            return

        runs = []
        for row in data:
            # Extract patchflow data
            patchflow_data = {
                "name": row.pop("p_name", None),
                "graph": row.pop("p_graph", {}),
            }

            # Create run with patchflow data
            run_data = dict(row)
            run_data["patchflow"] = patchflow_data
            runs.append(PatchflowRun(run_data))

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


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(check_and_run_pending())
    finally:
        loop.close()


def main_daemon():
    async def main_loop():
        wait_time = 30
        while True:
            try:
                await check_and_run_pending()
                await asyncio.sleep(wait_time)
            except asyncio.CancelledError:
                log.info("Main loop cancelled")
                break

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
