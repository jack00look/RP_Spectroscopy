import time
import influxdb_client
from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from typing import Dict, Any, Optional

class GrafanaManager:
    """
    Manages communication with InfluxDB for visualization in Grafana.
    """
    
    def __init__(self, 
                 bucket: str = "locking_parameters", 
                 org: str = "lab_bec1", 
                 url: str = "http://localhost:8086", 
                 token: str = "VG0O9fEgoMWlKrn83VwaoU6w3IhfP3l-WJqF0kQCArYT2MdwPK-rgO68oH7_awXlnYyDYzCWDbOsbdY4kkJ0UA=="):
        """
        Initialize the InfluxDB client.
        
        :param bucket: InfluxDB bucket name.
        :param org: InfluxDB organization name.
        :param url: InfluxDB server URL.
        :param token: InfluxDB authentication token.
        """
        self.bucket = bucket
        self.org = org
        self.url = url
        self.token = token
        
        self.client = influxdb_client.InfluxDBClient(
            url=self.url,
            token=self.token,
            org=self.org
        )
        
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

    def send_point(self, 
                   measurement: str, 
                   fields: Dict[str, Any], 
                   tags: Optional[Dict[str, str]] = None, 
                   timestamp_ns: Optional[int] = None):
        """
        Send a generic point to InfluxDB.
        
        :param measurement: Name of the measurement.
        :param fields: Dictionary of field values.
        :param tags: Optional dictionary of tags.
        :param timestamp_ns: Optional timestamp in nanoseconds. Defaults to current time.
        """
        point = Point(measurement)
        
        # Add tags
        if tags:
            for key, value in tags.items():
                point.tag(key, value)
        
        # Add fields
        for key, value in fields.items():
            point.field(key, value)
            
        # Add timestamp
        if timestamp_ns is None:
            timestamp_ns = time.time_ns()
            
        point.time(timestamp_ns, WritePrecision.NS)
        
        try:
            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
        except Exception as e:
            print(f"Error writing to InfluxDB: {e}")

    def log_lock_status(self, device_name: str, line_name: str, is_locked: bool, monitor_mean: float):
        """
        Specialized method to log laser lock status.
        
        :param device_name: Name of the board (e.g., 'Potassium_D2').
        :param line_name: Name of the line being locked.
        :param is_locked: Boolean status of the lock.
        :param monitor_mean: Mean value of the monitor signal.
        """
        fields = {
            "is_locked": int(is_locked),  # Store as 0/1 for easier plotting
            "monitor_mean": monitor_mean
        }
        tags = {
            "device": device_name,
            "line": line_name
        }
        self.send_point("laser_lock_telemetry", fields, tags)

    def close(self):
        """Close the InfluxDB client connection."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
