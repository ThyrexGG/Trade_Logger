import psycopg2

project_ref = "wutzxzophrfkqpylcswc"
password = "tBmCrXHFkbov8r5o"
user = f"postgres.{project_ref}"

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
]

for r in regions:
    host = f"{r}.pooler.supabase.com"
    for port in [6543, 5432]:
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname="postgres",
                user=user,
                password=password,
                connect_timeout=4
            )
            print(f"SUCCESS! Connected via region: {r}, port: {port}")
            cur = conn.cursor()
            cur.execute("SELECT version();")
            print("Version:", cur.fetchone())
            conn.close()
            exit(0)
        except Exception as e:
            # print(f"Failed {r}:{port} -> {e}")
            pass

print("Finished testing regions.")
