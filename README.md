# Patchflow Run Checker

A script that checks Supabase for pending private patchflow runs and triggers the patchflow command for each matching run.

## Prerequisites

- Python 3.12+ (as specified in pyproject.toml)
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and virtual environment manager

## Setup

1. Clone this repository
2. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Edit `.env` and add your Supabase credentials:
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_ANON_KEY=your_anon_key
   SUPABASE_USER_EMAIL=your_email
   SUPABASE_USER_PASSWORD=your_password
   ```
4. Install dependencies using uv:
   ```bash
   uv sync
   ```

5. Make the script executable:
   ```bash
   chmod +x check_pending_runs.py
   ```

## Usage

Run the script manually:
```bash
./check_pending_runs.py
```

### Setting up as a Cron Job

To run the script every 5 minutes, add this line to your crontab:
```bash
*/5 * * * * /path/to/check_pending_runs.py >> /path/to/logfile.log 2>&1
```

To edit your crontab:
```bash
crontab -e
```

## Project Structure

- `pyproject.toml`: Project configuration and dependencies
- `check_pending_runs.py`: Main script
- `.env.example`: Example environment variables
- `.gitignore`: Git ignore rules

## Dependencies

The project uses the following main dependencies (as specified in pyproject.toml):
- python-dotenv>=1.1.0
- supabase>=2.15.0

## Authentication

The script uses Supabase authentication with:
- Anon key for initial client setup
- Email and password for user authentication
- The authenticated session is used to query the database

## Logging

The script logs:
- Authentication status
- When it starts processing a run
- Success messages for each triggered run
- Any errors that occur during processing

## Error Handling

The script includes error handling for:
- Authentication failures
- Supabase connection issues
- Failed patchflow command execution
- General exceptions

## Environment Variables

- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_ANON_KEY`: Your Supabase anon/public key
- `SUPABASE_USER_EMAIL`: Email for authentication
- `SUPABASE_USER_PASSWORD`: Password for authentication
