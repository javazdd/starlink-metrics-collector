import time
import requests
import logging
import os
import subprocess
import socket
import json
import re
import statistics

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class EnhancedStarlinkCollector:
    def __init__(self):
        self.starlink_ip = os.getenv("STARLINK_IP", "192.168.1.1")
        self.datadog_host = os.getenv("DATADOG_HOST", "172.17.0.3")
        self.datadog_port = int(os.getenv("DATADOG_PORT", "8125"))
        self.collection_interval = int(os.getenv("COLLECTION_INTERVAL", "60"))
        self.version = os.getenv("VERSION", "v1.2.1")
        self.environment = os.getenv("ENVIRONMENT", "prod")
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.historical_metrics = []
        logger.info(f"Enhanced Starlink collector v{self.version} with Service Checks - IP: {self.starlink_ip}, Datadog: {self.datadog_host}:{self.datadog_port}")
    
    def send_metric(self, metric_name, value, metric_type="g"):
        """Send metrics to Datadog via DogStatsD"""
        try:
            tags = f"service:network,device:starlink,segment:WAN,version:{self.version},env:{self.environment}"
            metric_data = f"{metric_name}:{value}|{metric_type}|#{tags}".encode("utf-8")
            self.sock.sendto(metric_data, (self.datadog_host, self.datadog_port))
        except Exception as e:
            logger.error(f"Failed to send metric {metric_name}: {e}")
    
    def send_service_check(self, check_name, status, message=None):
        """Send service checks to Datadog via DogStatsD
        
        Args:
            check_name (str): Name of the service check
            status (int): 0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN
            message (str): Optional message describing the status
        """
        try:
            tags = f"service:network,device:starlink,segment:WAN,version:{self.version},env:{self.environment}"
            timestamp = int(time.time())
            
            # DogStatsD service check format: _sc|<name>|<status>|d:<timestamp>|h:<hostname>|#<tags>|m:<message>
            service_check_data = f"_sc|{check_name}|{status}|d:{timestamp}|#{tags}"
            
            if message:
                # Escape special characters in message
                escaped_message = message.replace("|", "\\|").replace("\n", "\\n")
                service_check_data += f"|m:{escaped_message}"
            
            self.sock.sendto(service_check_data.encode("utf-8"), (self.datadog_host, self.datadog_port))
            
        except Exception as e:
            logger.error(f"Failed to send service check {check_name}: {e}")
    
    def get_http_performance_metrics(self):
        """Enhanced HTTP performance metrics using curl"""
        try:
            curl_format = """total_time:%{time_total}
namelookup_time:%{time_namelookup}
connect_time:%{time_connect}
appconnect_time:%{time_appconnect}
pretransfer_time:%{time_pretransfer}
starttransfer_time:%{time_starttransfer}
size_download:%{size_download}
speed_download:%{speed_download}
speed_upload:%{speed_upload}
http_code:%{response_code}"""
            
            result = subprocess.run([
                "curl", "-s", "-w", curl_format, 
                f"http://{self.starlink_ip}", 
                "-o", "/dev/null", "--max-time", "10"
            ], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                metrics = {}
                for line in result.stdout.strip().split("\\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        try:
                            metrics[f"http_{key}"] = float(value)
                        except ValueError:
                            continue
                
                # Convert some metrics to more useful units
                if "http_namelookup_time" in metrics:
                    metrics["http_dns_resolution_ms"] = metrics["http_namelookup_time"] * 1000
                if "http_connect_time" in metrics:
                    metrics["http_tcp_connect_ms"] = metrics["http_connect_time"] * 1000
                if "http_starttransfer_time" in metrics:
                    metrics["http_time_to_first_byte_ms"] = metrics["http_starttransfer_time"] * 1000
                if "http_speed_download" in metrics and metrics["http_speed_download"] > 0:
                    metrics["http_download_speed_mbps"] = (metrics["http_speed_download"] * 8) / (1024 * 1024)
                
                return metrics
                
        except Exception as e:
            logger.error(f"HTTP performance test failed: {e}")
            return None
    
    def get_enhanced_ping_metrics(self):
        """Enhanced ping metrics with detailed statistics"""
        try:
            result = subprocess.run([
                "ping", "-c", "30", "-i", "0.1", 
                self.starlink_ip
            ], capture_output=True, text=True, timeout=35)
            
            if result.returncode == 0:
                lines = result.stdout.split("\\n")
                metrics = {}
                ping_times = []
                
                # Extract individual ping times
                for line in lines:
                    if "time=" in line:
                        time_match = re.search(r"time=([0-9.]+)", line)
                        if time_match:
                            ping_times.append(float(time_match.group(1)))
                
                # Parse packet loss
                packet_loss = 0
                for line in lines:
                    if "packet loss" in line:
                        loss_match = re.search(r"([0-9.]+)%\\s+packet\\s+loss", line)
                        if loss_match:
                            packet_loss = float(loss_match.group(1))
                            break
                
                # Parse timing stats (min/avg/max/mdev)
                for line in lines:
                    if "min/avg/max" in line and "=" in line:
                        stats_part = line.split("=")[1].strip()
                        if "/" in stats_part:
                            parts = stats_part.split("/")
                            if len(parts) >= 4:
                                metrics.update({
                                    "ping_min_ms": float(parts[0]),
                                    "ping_avg_ms": float(parts[1]),
                                    "ping_max_ms": float(parts[2]),
                                    "ping_mdev_ms": float(parts[3].split()[0])
                                })
                            break
                
                # Calculate additional statistics
                if ping_times:
                    metrics.update({
                        "ping_median_ms": statistics.median(ping_times),
                        "ping_stdev_ms": statistics.stdev(ping_times) if len(ping_times) > 1 else 0,
                        "ping_95th_percentile_ms": statistics.quantiles(ping_times, n=20)[18] if len(ping_times) >= 20 else max(ping_times),
                        "ping_packet_count": len(ping_times)
                    })
                
                metrics.update({
                    "ping_success_rate": 100.0 - packet_loss,
                    "ping_drop_rate": packet_loss,
                })
                
                if "ping_max_ms" in metrics and "ping_min_ms" in metrics:
                    metrics["ping_jitter_ms"] = metrics["ping_max_ms"] - metrics["ping_min_ms"]
                
                return metrics
                
        except Exception as e:
            logger.error(f"Enhanced ping test failed: {e}")
            return None
    
    def get_quality_scores(self, ping_metrics, http_metrics):
        """Calculate derived quality and performance scores"""
        try:
            scores = {}
            
            # Latency Quality Score (0-100, higher is better)
            if ping_metrics and "ping_avg_ms" in ping_metrics:
                avg_ping = ping_metrics["ping_avg_ms"]
                if avg_ping <= 1:
                    latency_score = 100
                elif avg_ping <= 10:
                    latency_score = 100 - (avg_ping - 1) * 5
                elif avg_ping <= 50:
                    latency_score = 50 - (avg_ping - 10) * 1.25
                else:
                    latency_score = 0
                scores["quality_latency_score"] = max(0, min(100, latency_score))
            
            # Stability Score based on jitter and packet loss
            if ping_metrics:
                stability_score = 100
                if "ping_drop_rate" in ping_metrics:
                    stability_score -= ping_metrics["ping_drop_rate"] * 2
                if "ping_mdev_ms" in ping_metrics:
                    jitter_penalty = min(ping_metrics["ping_mdev_ms"] * 10, 50)
                    stability_score -= jitter_penalty
                scores["quality_stability_score"] = max(0, min(100, stability_score))
            
            # HTTP Performance Score
            if http_metrics and "http_time_to_first_byte_ms" in http_metrics:
                ttfb = http_metrics["http_time_to_first_byte_ms"]
                if ttfb <= 5:
                    http_score = 100
                elif ttfb <= 50:
                    http_score = 100 - (ttfb - 5) * 2
                else:
                    http_score = max(0, 10 - (ttfb - 50) * 0.2)
                scores["quality_http_score"] = max(0, min(100, http_score))
            
            # Overall Connection Quality
            if len(scores) >= 2:
                weights = {"quality_latency_score": 0.4, "quality_stability_score": 0.4, "quality_http_score": 0.2}
                weighted_sum = sum(scores.get(metric, 0) * weights.get(metric, 0) for metric in weights)
                scores["quality_overall_score"] = weighted_sum
            
            return scores
            
        except Exception as e:
            logger.error(f"Quality score calculation failed: {e}")
            return {}
    
    def get_speed_estimate(self):
        """Improved speed estimation with multiple tests"""
        try:
            speeds = []
            
            for i in range(3):
                start_time = time.time()
                response = requests.get(f"http://{self.starlink_ip}", timeout=8, stream=True)
                
                total_bytes = 0
                for chunk in response.iter_content(chunk_size=8192):
                    total_bytes += len(chunk)
                    if time.time() - start_time > 2:
                        break
                
                duration = time.time() - start_time
                if duration > 0 and total_bytes > 0:
                    speed_mbps = (total_bytes * 8) / (duration * 1024 * 1024)
                    speeds.append(speed_mbps)
                
                time.sleep(0.5)
            
            if speeds:
                return {
                    "estimated_download_mbps": statistics.mean(speeds),
                    "download_speed_max_mbps": max(speeds),
                    "download_speed_min_mbps": min(speeds),
                    "download_speed_consistency": (min(speeds) / max(speeds)) * 100 if max(speeds) > 0 else 0
                }
                
        except Exception as e:
            logger.error(f"Speed test failed: {e}")
            return None
    
    def calculate_trends(self, current_metrics):
        """Calculate performance trends over time"""
        try:
            self.historical_metrics.append({
                "timestamp": time.time(),
                "metrics": current_metrics.copy()
            })
            
            if len(self.historical_metrics) > 10:
                self.historical_metrics.pop(0)
            
            trends = {}
            
            if len(self.historical_metrics) >= 3:
                key_metrics = ["ping_avg_ms", "estimated_download_mbps", "quality_overall_score"]
                
                for metric in key_metrics:
                    values = []
                    for hist in self.historical_metrics:
                        if metric in hist["metrics"]:
                            values.append(hist["metrics"][metric])
                    
                    if len(values) >= 3:
                        if values[0] != 0:
                            trend_pct = ((values[-1] - values[0]) / values[0]) * 100
                            trends[f"{metric}_trend_pct"] = trend_pct
                        
                        if len(values) > 1:
                            trends[f"{metric}_volatility"] = statistics.stdev(values)
            
            return trends
            
        except Exception as e:
            logger.error(f"Trend calculation failed: {e}")
            return {}
    
    def send_service_checks(self, ping_metrics, quality_scores, http_metrics):
        """Send appropriate service checks based on metrics"""
        try:
            # 1. Starlink Connectivity Service Check
            if ping_metrics and "ping_success_rate" in ping_metrics:
                success_rate = ping_metrics["ping_success_rate"]
                if success_rate >= 95:
                    self.send_service_check("starlink.connectivity", 0, f"Starlink connected - {success_rate:.1f}% success rate")
                elif success_rate >= 80:
                    self.send_service_check("starlink.connectivity", 1, f"Starlink connectivity degraded - {success_rate:.1f}% success rate")
                else:
                    self.send_service_check("starlink.connectivity", 2, f"Starlink connectivity critical - {success_rate:.1f}% success rate")
            else:
                self.send_service_check("starlink.connectivity", 3, "Unable to determine connectivity status")
            
            # 2. Starlink Performance Service Check
            if quality_scores and "quality_overall_score" in quality_scores:
                overall_score = quality_scores["quality_overall_score"]
                if overall_score >= 80:
                    self.send_service_check("starlink.performance", 0, f"Excellent performance - {overall_score:.1f}/100 score")
                elif overall_score >= 60:
                    self.send_service_check("starlink.performance", 1, f"Good performance - {overall_score:.1f}/100 score")
                elif overall_score >= 40:
                    self.send_service_check("starlink.performance", 1, f"Fair performance - {overall_score:.1f}/100 score")
                else:
                    self.send_service_check("starlink.performance", 2, f"Poor performance - {overall_score:.1f}/100 score")
            
            # 3. Starlink Latency Service Check
            if ping_metrics and "ping_avg_ms" in ping_metrics:
                avg_ping = ping_metrics["ping_avg_ms"]
                if avg_ping <= 5:
                    self.send_service_check("starlink.latency", 0, f"Excellent latency - {avg_ping:.1f}ms average")
                elif avg_ping <= 20:
                    self.send_service_check("starlink.latency", 1, f"Good latency - {avg_ping:.1f}ms average")
                elif avg_ping <= 50:
                    self.send_service_check("starlink.latency", 1, f"Fair latency - {avg_ping:.1f}ms average")
                else:
                    self.send_service_check("starlink.latency", 2, f"High latency - {avg_ping:.1f}ms average")
            
            # 4. Starlink Stability Service Check  
            if ping_metrics and "ping_drop_rate" in ping_metrics:
                packet_loss = ping_metrics["ping_drop_rate"]
                jitter = ping_metrics.get("ping_mdev_ms", 0)
                
                if packet_loss == 0 and jitter <= 1:
                    self.send_service_check("starlink.stability", 0, f"Excellent stability - 0% loss, {jitter:.1f}ms jitter")
                elif packet_loss <= 1 and jitter <= 5:
                    self.send_service_check("starlink.stability", 1, f"Good stability - {packet_loss:.1f}% loss, {jitter:.1f}ms jitter")
                elif packet_loss <= 5 and jitter <= 10:
                    self.send_service_check("starlink.stability", 1, f"Fair stability - {packet_loss:.1f}% loss, {jitter:.1f}ms jitter")
                else:
                    self.send_service_check("starlink.stability", 2, f"Poor stability - {packet_loss:.1f}% loss, {jitter:.1f}ms jitter")
                    
        except Exception as e:
            logger.error(f"Failed to send service checks: {e}")
    
    def run(self):
        logger.info("Starting Enhanced Starlink Metrics Collector v2.1 with Service Checks...")
        
        while True:
            try:
                all_metrics = {}
                
                # Collect ping metrics
                ping_metrics = self.get_enhanced_ping_metrics()
                if ping_metrics:
                    all_metrics.update(ping_metrics)
                    avg_ping = ping_metrics.get("ping_avg_ms", 0)
                    success_rate = ping_metrics.get("ping_success_rate", 0)
                    mdev = ping_metrics.get("ping_mdev_ms", 0)
                    logger.info(f"Ping: {avg_ping:.1f}ms avg, {mdev:.1f}ms jitter, {success_rate:.1f}% success")
                
                # Collect HTTP metrics
                http_metrics = self.get_http_performance_metrics()
                if http_metrics:
                    all_metrics.update(http_metrics)
                    ttfb = http_metrics.get("http_time_to_first_byte_ms", 0)
                    http_speed = http_metrics.get("http_download_speed_mbps", 0)
                    logger.info(f"HTTP: {ttfb:.1f}ms TTFB, {http_speed:.2f} Mbps")
                
                # Collect speed metrics
                speed_metrics = self.get_speed_estimate()
                if speed_metrics:
                    all_metrics.update(speed_metrics)
                    est_speed = speed_metrics.get("estimated_download_mbps", 0)
                    consistency = speed_metrics.get("download_speed_consistency", 0)
                    logger.info(f"Speed: {est_speed:.2f} Mbps avg, {consistency:.1f}% consistency")
                
                # Calculate quality scores
                quality_scores = self.get_quality_scores(ping_metrics, http_metrics)
                if quality_scores:
                    all_metrics.update(quality_scores)
                    overall_score = quality_scores.get("quality_overall_score", 0)
                    logger.info(f"Quality: {overall_score:.1f}/100 overall score")
                
                # Calculate trends
                trends = self.calculate_trends(all_metrics)
                if trends:
                    all_metrics.update(trends)
                
                # Send Service Checks (replaces connectivity metric)
                self.send_service_checks(ping_metrics, quality_scores, http_metrics)
                service_checks_sent = 4  # connectivity, performance, latency, stability
                
                # Send regular metrics (excluding connectivity)
                if all_metrics:
                    metrics_sent = 0
                    for metric_name, value in all_metrics.items():
                        if isinstance(value, (int, float)) and not (value != value):
                            self.send_metric(f"starlink.{metric_name}", value)
                            metrics_sent += 1
                    
                    # Send total counts
                    self.send_metric("starlink.total_metrics", len(all_metrics))
                    self.send_metric("starlink.service_checks_sent", service_checks_sent)
                    
                    logger.info(f"Successfully sent {metrics_sent} metrics and {service_checks_sent} service checks to Datadog")
                else:
                    self.send_service_check("starlink.connectivity", 3, "No metrics collected - service unknown")
                    logger.warning("No metrics collected")
                
                time.sleep(self.collection_interval)
                
            except KeyboardInterrupt:
                logger.info("Shutting down enhanced collector...")
                break
            except Exception as e:
                logger.error(f"Collection error: {e}")
                self.send_service_check("starlink.connectivity", 2, f"Collection error: {str(e)}")
                time.sleep(30)

if __name__ == "__main__":
    collector = EnhancedStarlinkCollector()
    collector.run()
