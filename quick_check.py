import requests

services = {
    "后端API": "https://wstest-backend.onrender.com",
    "用户页面": "https://wsprj.onrender.com",
    "管理后台": "https://wsprj-admin.onrender.com"
}

print("="*60)
print("Render服务健康检查")
print("="*60)

for name, url in services.items():
    try:
        r = requests.get(f"{url}/health", timeout=10)
        status = "OK" if r.status_code == 200 else "FAIL"
        print(f"{name}: [{status}] {r.status_code}")
    except Exception as e:
        print(f"{name}: [FAIL] {str(e)}")

print("="*60)
