import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from GettingStarted_lib.grafana_manager import GrafanaManager

def test_grafana():
    print("--- Testing GrafanaManager ---")
    try:
        with GrafanaManager() as gm:
            print("Sending test point...")
            gm.send_point(
                measurement="test_connection",
                fields={"value": 1.23, "status": "ok"},
                tags={"source": "test_script"}
            )
            
            print("Sending lock telemetry...")
            gm.log_lock_status(
                device_name="Test_Device",
                line_name="Test_Line",
                is_locked=True,
                monitor_mean=0.85
            )
            print("Successfully sent points to InfluxDB (check Grafana/Influx UI).")
    except Exception as e:
        print(f"Failed to communicate with Grafana/Influx: {e}")

if __name__ == "__main__":
    test_grafana()
