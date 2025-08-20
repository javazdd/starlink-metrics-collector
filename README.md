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

## Metrics (namespace: `starlink.*`)

The collector emits the following Datadog DogStatsD metrics, all prefixed with `starlink.`:

- starlink.ping_min_ms
- starlink.ping_avg_ms
- starlink.ping_max_ms
- starlink.ping_mdev_ms
- starlink.ping_median_ms
- starlink.ping_stdev_ms
- starlink.ping_95th_percentile_ms
- starlink.ping_packet_count
- starlink.ping_success_rate
- starlink.ping_drop_rate
- starlink.ping_jitter_ms
- starlink.http_total_time
- starlink.http_namelookup_time
- starlink.http_connect_time
- starlink.http_appconnect_time
- starlink.http_pretransfer_time
- starlink.http_starttransfer_time
- starlink.http_size_download
- starlink.http_speed_download
- starlink.http_speed_upload
- starlink.http_http_code
- starlink.http_dns_resolution_ms
- starlink.http_tcp_connect_ms
- starlink.http_time_to_first_byte_ms
- starlink.http_download_speed_mbps
- starlink.estimated_download_mbps
- starlink.download_speed_max_mbps
- starlink.download_speed_min_mbps
- starlink.download_speed_consistency
- starlink.quality_latency_score
- starlink.quality_stability_score
- starlink.quality_http_score
- starlink.quality_overall_score
- starlink.ping_avg_ms_trend_pct
- starlink.ping_avg_ms_volatility
- starlink.estimated_download_mbps_trend_pct
- starlink.estimated_download_mbps_volatility
- starlink.quality_overall_score_trend_pct
- starlink.quality_overall_score_volatility
- starlink.total_metrics
- starlink.service_checks_sent

## Service Checks

The collector also emits Datadog service checks:

- starlink.connectivity
- starlink.performance
- starlink.latency
- starlink.stability

## License

This project is provided as-is for educational and monitoring purposes.
