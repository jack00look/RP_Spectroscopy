from GettingStarted_lib.grafana_manager import GrafanaManager
from time import sleep
# The manager handles credentials automatically
with GrafanaManager() as gm:
    gm.send_point("experiment_1", {"temperature": 22.5, "pressure": 1013})
    
    # Specific for laser lock telemetry
    gm.log_lock_status(
        device_name="Potassium_D2", 
        line_name="LINE_K_D2", 
        is_locked=False, 
        monitor_mean=0.94
    )
    sleep(5)
    gm.log_lock_status(
        device_name="Potassium_D2", 
        line_name="LINE_K_D2", 
        is_locked=True, 
        monitor_mean=0.94
    )
