
import requests

url = "http://localhost:8000/recommend"

data = {
"userId":"U1",
"query":"iphone"
}

r = requests.post(url, json=data)

print(r.json())
