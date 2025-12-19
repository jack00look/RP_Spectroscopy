import requests
import time

url = "http://localhost:8080/telegraf"

timestamp = int(time.time() * 1e9)

line = (
    "Locking_parameters,"
    "device=Potassium_D2,room=BEC_1 "
    "locked=1,"
    "voltage_offset=0.93,"
    "amplitude=0.9,"
    "offset_a=-0.0068 "
    f"{timestamp}\n"
)

headers = {"Content-Type": "text/plain"}

r = requests.post(url, data=line, headers=headers)
print("Status:", r.status_code)
