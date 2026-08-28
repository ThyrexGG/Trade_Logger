import socket

project_ref = "wutzxzophrfkqpylcswc"
regions = [
    "aws-0-ap-southeast-1",
    "aws-0-ap-southeast-2",
    "aws-0-ap-south-1",
    "aws-0-ap-northeast-1",
    "aws-0-ap-northeast-2",
    "aws-0-us-east-1",
    "aws-0-us-west-1",
    "aws-0-eu-central-1",
    "aws-0-eu-west-1",
    "aws-0-eu-west-2",
    "aws-0-eu-west-3",
    "aws-0-ca-central-1",
    "aws-0-sa-east-1",
]

for r in regions:
    host = f"{r}.pooler.supabase.com"
    try:
        ip = socket.gethostbyname(host)
        print(f"Found pooler host {host} -> {ip}")
    except Exception as e:
        pass
