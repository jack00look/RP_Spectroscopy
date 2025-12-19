import requests
import time
import random
from time import sleep

url = "http://localhost:8080/telegraf"

while True:

    timestamp = int(time.time() * 1e9)

    random_number = random.uniform(-0.01, 0.01)

    line = (
        "Locking_parameters,"
        "device=Potassium_D2,room=BEC_1 "
        "locked=1,"
        "voltage_offset=0.93,"
        "amplitude=0.9,"
        f"offset_a={random_number} "
        f"{timestamp}\n"
    )

    headers = {"Content-Type": "text/plain"}

    r = requests.post(url, data=line, headers=headers)
    print("Status:", r.status_code)

    sleep(15)