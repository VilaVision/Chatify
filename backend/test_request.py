# test_request.py

import requests

url = "http://127.0.0.1:8000/process"
payload = {
    "url": "https://portfolio-eight-roan-53.vercel.app/",
    "max_pages": 20
}

response = requests.post(url, json=payload)

if response.status_code == 200:
    with open("chatbot_package.zip", "wb") as f:
        f.write(response.content)
    print("✅ Chatbot package downloaded as chatbot_package.zip")
else:
    print(f"❌ Error {response.status_code}: {response.text}")
