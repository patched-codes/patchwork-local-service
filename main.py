#!/usr/bin/env python3

import os
import subprocess

from dotenv import load_dotenv
from supabase import Client, create_client

# Load environment variables
load_dotenv()

# Initialize Supabase client with anon key
supabase_url = os.getenv("SUPABASE_URL")
supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_anon_key)


def authenticate_user():
    """Authenticate with username and password"""
    try:
        auth_response = supabase.auth.sign_in_with_password(
            {"email": os.getenv("SUPABASE_USER_EMAIL"), "password": os.getenv("SUPABASE_USER_PASSWORD")}
        )
        return auth_response
    except Exception as e:
        print(f"Authentication failed: {str(e)}")
        raise


def check_and_trigger_runs():
    try:
        # Authenticate user first
        authenticate_user()

        # Query for pending runs with is_private=true
        response = (
            supabase.table("custom_patchflow_runs")
            .select("id")
            .eq("status", "pending")
            .eq("meta->is_private", True)
            .execute()
        )

        # Process each pending run
        for run in response.data:
            run_id = run["id"]
            print(f"Triggering patchflow for run {run_id}")

            # Run patchflow command
            try:
                subprocess.run(["patchflow", f"RUN={run_id}"], check=True, capture_output=True, text=True)
                print(f"Successfully triggered patchflow for run {run_id}")
            except subprocess.CalledProcessError as e:
                print(f"Error triggering patchflow for run {run_id}: {e.stderr}")

    except Exception as e:
        print(f"Error checking pending runs: {str(e)}")


if __name__ == "__main__":
    check_and_trigger_runs()
