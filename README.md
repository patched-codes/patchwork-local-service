# Patchflow Local Service

A service that processes pending private patchflow runs from a PostgreSQL database and executes the patchflow command for each matching run.

## Prerequisites

- Python 3.12+ (as specified in pyproject.toml)
- PostgreSQL database access
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and virtual environment manager

## Setup

1. Clone this repository
2. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Edit `.env` and add your database credentials and configuration:
   ```
   DB_HOST=your_database_host
   DB_NAME=your_database_name
   DB_USER=your_database_user
   DB_PASSWORD=your_database_password
   DB_PORT=your_database_port
   ORGANIZATION_ID=your_organization_id
   PATCHWORK_EXEC=path_to_patchwork_executable
   OUTPUT_DIR=path_to_output_directory
   READ_ONLY=false  # Set to true for dry-run mode
   ```
4. Install dependencies using uv:
   ```bash
   uv sync
   ```

5. Make the script executable:
   ```bash
   chmod +x main.py
   ```

## Usage

Run the script manually:
```bash
./main.py
```

### Setting up as a Cron Job

To run the script every minute, add this line to your crontab:
```bash
* * * * *  /path_to_directory/.venv/bin/python /path_to_directory/main.py >> /path_to_logfile/logfile.log 2>&1
```

The script will:
1. Connect to the PostgreSQL database
2. Find pending private patchflow runs for your organization
3. For each pending run:
   - Execute the patchflow command with the run's inputs
   - Log the command output
   - Update the run's status and outputs in the database
4. Handle any errors that occur during processing

## Project Structure

- `pyproject.toml`: Project configuration and dependencies
- `main.py`: Main script for processing patchflow runs
- `.env.example`: Example environment variables
- `.gitignore`: Git ignore rules

## Dependencies

The project uses the following main dependencies (as specified in pyproject.toml):
- python-dotenv>=1.1.0
- psycopg2>=2.9.9
- strip-ansi>=0.1.1

## Logging

The script logs:
- Database connection status
- When it starts processing a run
- Command execution details
- Success/failure status for each run
- Any errors that occur during processing

## Error Handling

The script includes error handling for:
- Database connection issues
- Failed patchflow command execution
- File I/O operations
- General exceptions

## Environment Variables

- `DB_HOST`: PostgreSQL database host
- `DB_NAME`: PostgreSQL database name
- `DB_USER`: PostgreSQL database user
- `DB_PASSWORD`: PostgreSQL database password
- `DB_PORT`: PostgreSQL database port (default: 5432)
- `ORGANIZATION_ID`: Your organization ID
- `PATCHWORK_EXEC`: Path to the patchwork executable
- `OUTPUT_DIR`: Directory to store output files
- `READ_ONLY`: Set to "true" for dry-run mode (default: "false")
