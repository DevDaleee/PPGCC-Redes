import os
import json
import csv
import statistics

def read_app_log(filepath_json):
  with open(filepath_json, 'r') as f:
    dada = json.load(f)

  return dada['summary']

def read_network_log(filepath_csv):
  total_network_bytes = 0
  first_ts = 0.0
  last_ts = 0.0
  with open(filepath_csv, 'r') as f:
    reader = csv.DictReader(f)
    for line in reader:
      length = int(line['frame.len'])
      total_network_bytes += length

      ts = float(line['frame.time_relative'])
      if first_ts == 0: first_ts = ts
      last_ts = ts
  network_duration = last_ts - first_ts
  return total_network_bytes, network_duration

def validate_experiment(app_json, network_csv):
  resume_app = read_app_log(app_json)
  network_bytes, network_time = read_network_log(network_csv)

  app_bytes = resume_app['bytes_total']

  print(f"Aplicação enviou: {app_bytes} bytes")
  print(f"Rede capturou: {network_bytes} bytes")

  #Diferença (overhead de cabeçalhos e retrasmissões)
  overhead = (network_bytes - app_bytes) / app_bytes * 100
  print(f"Overhead da rede: {overhead:.2f}%")
