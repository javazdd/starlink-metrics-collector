import time
import requests
import logging
import os
import subprocess
import socket
import json
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class StarlinkCollector:
    def __init__(self):
        self.starlink_ip = os.getenv("STARLINK_IP", "192.168.1.1")
        self.datadog_host = os.getenv("DATADOG_HOST", "172.17.0.4")
        self.datadog_port = int(os.getenv("DATADOG_PORT", "8125"))
        self.collection_interval = int(os.getenv("COLLECTION_INTERVAL", "60"))
        self.version = os.getenv("VERSION", "1.00")
        self.environment = os.getenv("ENVIRONMENT", "prod")
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        logger.info(f"Enhanced Starlink collector - IP: {self.starlink_ip}")
    
    def send_metric(self, metric_name, value, metric_type="g"):
        try:
            # Add tags to the metric in StatsD format
            tags = f"service:network,device:starlink,segment:WAN,version:{self.version},env:{self.environment}"
            metric_data = f"{metric_name}:{value}|{metric_type}|#{tags}".encode("utf-8")
            self.sock.sendto(metric_data, (self.datadog_host, self.datadog_port))
        except Exception as e:
            logger.error(f"Failed to send metric {metric_name}: {e}")
    
    def scrape_starlink_web_interface(self):
        try:
            from bs4 import BeautifulSoup
            
            response = requests.get(f"http://{self.starlink_ip}", timeout=10)
            if response.status_code == 200:
                text = response.text.lower()
                metrics = {}
                
                # Extract latency
                latency_match = re.search(r"latency[\s:]*([0-9.]+)\s*ms", text)
                if latency_match:
                    metrics["web_latency_ms"] = float(latency_match.group(1))
                
                # Extract throughput
                download_match = re.search(r"download[\s:]*([0-9.]+)\s*mbps", text)
                if download_match:
                    metrics["web_download_mbps"] = float(download_match.group(1))
                
                upload_match = re.search(r"upload[\s:]*([0-9.]+)\s*mbps", text)
                if upload_match:
                    metrics["web_upload_mbps"] = float(upload_match.group(1))
                
                # Extract power
                power_match = re.search(r"power[\s\w]*[:\s]*([0-9.]+)\s*w", text)
                if power_match:
                    metrics["web_power_draw_watts"] = float(power_match.group(1))
                
                # Extract ping success
                ping_success_match = re.search(r"ping[\s\w]*success[\s:]*([0-9.]+)%", text)
                if ping_success_match:
                    metrics["web_ping_success_rate"] = float(ping_success_match.group(1))
                
                return metrics if metrics else None
                
        except ImportError:
            logger.warning("BeautifulSoup not available")
            return None
        except Exception as e:
            logger.error(f"Web scraping failed: {e}")
            return None
    
    def get_ping_metrics(self):
        try:
            result = subprocess.run(["ping", "-c", "20", "-i", "0.2", self.starlink_ip], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                lines = result.stdout.split("\n")
                metrics = {}
                
                # Parse packet loss
                packet_loss = 0
                for line in lines:
                    if "packet loss" in line:
                        loss_match = re.search(r"([0-9.]+)%\s+packet\s+loss", line)
                        if loss_match:
                            packet_loss = float(loss_match.group(1))
                            break
                
                # Parse timing stats
                for line in lines:
                    if "min/avg/max" in line:
                        stats = re.search(r"([0-9.]+)/([0-9.]+)/([0-9.]+)", line.split("=")[1])
                        if stats:
                            metrics.update({
                                "ping_min_ms": float(stats.group(1)),
                                "ping_avg_ms": float(stats.group(2)),
                                "ping_max_ms": float(stats.group(3)),
                                "ping_success_rate": 100.0 - packet_loss,
                                "ping_drop_rate": packet_loss,
                                "ping_jitter_ms": float(stats.group(3)) - float(stats.group(1))
                            })
                            break
                
                return metrics
                
        except Exception as e:
            logger.error(f"Ping test failed: {e}")
            return None
    
    def get_speed_estimate(self):
        try:
            start_time = time.time()
            response = requests.get(f"http://{self.starlink_ip}", timeout=10, stream=True)
            
            total_bytes = 0
            for chunk in response.iter_content(chunk_size=8192):
                total_bytes += len(chunk)
                if time.time() - start_time > 3:
                    break
            
            duration = time.time() - start_time
            if duration > 0 and total_bytes > 0:
                speed_mbps = (total_bytes * 8) / (duration * 1024 * 1024)
                return {
                    "estimated_download_mbps": speed_mbps,
                    "http_response_time_ms": duration * 1000
                }
                
        except Exception as e:
            logger.error(f"Speed test failed: {e}")
            return None
    
    def run(self):
        logger.info("Starting Enhanced Starlink Metrics Collector with tags...")
        
        while True:
            try:
                all_metrics = {}
                
                # Method 1: Enhanced ping metrics
                ping_metrics = self.get_ping_metrics()
                if ping_metrics:
                    all_metrics.update(ping_metrics)
                    avg_ping = ping_metrics.get("ping_avg_ms", 0)
                    success_rate = ping_metrics.get("ping_success_rate", 0)
                    logger.info(f"Ping: {avg_ping:.1f}ms avg, {success_rate:.1f}% success")
                
                # Method 2: Web interface scraping
                web_metrics = self.scrape_starlink_web_interface()
                if web_metrics:
                    all_metrics.update(web_metrics)
                    logger.info(f"Web scraping found {len(web_metrics)} additional metrics")
                
                # Method 3: Speed estimation
                speed_metrics = self.get_speed_estimate()
                if speed_metrics:
                    all_metrics.update(speed_metrics)
                    est_speed = speed_metrics.get("estimated_download_mbps", 0)
                    logger.info(f"Speed estimate: {est_speed:.2f} Mbps")
                
                # Send metrics to Datadog
                if all_metrics:
                    metrics_sent = 0
                    for metric_name, value in all_metrics.items():
                        if isinstance(value, (int, float)) and not (value != value):
                            self.send_metric(f"starlink.{metric_name}", value)
                            metrics_sent += 1
                    
                    self.send_metric("starlink.connectivity", 1)
                    self.send_metric("starlink.total_metrics", len(all_metrics))
                    
                    logger.info(f"Successfully sent {metrics_sent} Starlink metrics to Datadog with tags")
                else:
                    self.send_metric("starlink.connectivity", 0)
                    logger.warning("No metrics collected")
                
                time.sleep(self.collection_interval)
                
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error(f"Collection error: {e}")
                time.sleep(30)

collector = StarlinkCollector()
collector.run()
