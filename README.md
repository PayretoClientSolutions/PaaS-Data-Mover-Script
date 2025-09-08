# GCS Bulk Upload Script

A Python script that automatically uploads files in bulk to Google Cloud Storage (GCS) and organizes them into a "sent" folder after successful upload.

## Overview

This script is designed to run on a scheduled basis via cron on our Linux VM. It processes files from a specified directory, uploads them to a GCS bucket, and moves the successfully uploaded files to a "sent" folder for organization.

## Prerequisites

### System Requirements

- Linux VM (Ubuntu/Debian recommended)
- Python 3.8 or higher
- uv package manager
- Cron daemon (usually pre-installed on Linux systems)

### GCS Setup

- Google Cloud Storage bucket with appropriate permissions
- Service account with Storage Object Admin role
- Service account key file (`gcs.json`)
- Bucket named 'aci_raw'

## Logging

The script logs all activities to `app.log` by default. Log entries include:

- Upload start/completion times
- Successfully uploaded files
- Failed uploads with error messages
- File movement operations
- Any configuration issues

## Maintenance

### Regular Tasks

- Monitor log files for errors
- Check disk space on VM
- Verify GCS bucket storage usage
- Review and rotate logs as needed

## Dependencies

See `pyproject.toml` for complete list. Main dependencies:

- `google-cloud-storage`: GCS client library
- `python-dotenv`: Environment variable management
- Additional utilities for file handling and logging
