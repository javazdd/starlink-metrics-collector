# Starlink Metrics Collector

A Python script to collect metrics from Starlink satellite internet terminals for monitoring and analysis.

## Description

This project contains a Python script that collects network performance metrics from Starlink terminals. The script is designed to run in a Docker container for easy deployment and monitoring.

## Files

- `starlink_collector.py` - Main Python script for collecting Starlink metrics

## Usage

The script can be run standalone or in a Docker container:

### Docker Container Setup

The script is designed to run in a Docker container with the following configuration:

```bash
docker run -d \
  --name starlink-metrics-collector \
  -v /path/to/starlink_collector.py:/app/collector.py \
  python:3.11-slim \
  python /app/collector.py
```

### Requirements

- Python 3.11+
- Network access to Starlink terminal

## Configuration

Update the script configuration as needed for your specific Starlink terminal setup and monitoring requirements.

## License

This project is provided as-is for educational and monitoring purposes.
