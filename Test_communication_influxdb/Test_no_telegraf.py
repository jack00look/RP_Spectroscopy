import time
import os
import influxdb_client
from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# Configuration
token = "VG0O9fEgoMWlKrn83VwaoU6w3IhfP3l-WJqF0kQCArYT2MdwPK-rgO68oH7_awXlnYyDYzCWDbOsbdY4kkJ0UA=="
org = "lab_bec1"
bucket = "locking_parameters"
url = "http://localhost:8086"

# Create client
client = influxdb_client.InfluxDBClient(
    url=url,
    token=token,
    org=org
)

write_api = client.write_api(write_options=SYNCHRONOUS)

for value in range(10):
    point = (
        Point("measurement1")
        .tag("device", "Potassium_D2")
        .field("field1", value)
        .time(time.time_ns(), WritePrecision.NS)
    )

    write_api.write(bucket=bucket, org=org, record=point)
    print("Wrote:", value)
    time.sleep(1)

query_api = client.query_api()

query = """from(bucket: "locking_parameters")
 |> range(start: -10m)
 |> filter(fn: (r) => r._measurement == "measurement1")
 |> mean()"""
tables = query_api.query(query, org="lab_bec1")

for table in tables:
  for record in table.records:
    print(record)

client.close()