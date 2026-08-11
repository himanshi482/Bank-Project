import json
import urllib.request
import urllib.error

url = 'http://127.0.0.1:5000/api/send-otp'
data = json.dumps({'email': 'test@example.com', 'action': 'LOGIN'}).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        print(resp.status)
        print(resp.read().decode())
except urllib.error.HTTPError as e:
    print('HTTP', e.code)
    print(e.read().decode())
except Exception as e:
    print('ERROR', e)
