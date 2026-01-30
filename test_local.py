#!/usr/bin/env python3
import json
import urllib.request
import urllib.error

# Workflow'u yükle (Yeni native ComfyUI workflow)
with open('wan22_t2v_working.json', 'r') as f:
    prompt = json.load(f)

# Test parametreleri uygula
# Text prompts
prompt["89"]["inputs"]["text"] = "A cat walking on the street, cinematic shot, high quality"
prompt["72"]["inputs"]["text"] = "bright tones, overexposed, static, blurred details"

# Sampler settings
total_steps = 4
prompt["81"]["inputs"]["noise_seed"] = 42
prompt["81"]["inputs"]["cfg"] = 1.0
prompt["81"]["inputs"]["steps"] = total_steps
prompt["81"]["inputs"]["end_at_step"] = total_steps // 2

prompt["78"]["inputs"]["noise_seed"] = 0
prompt["78"]["inputs"]["cfg"] = 1.0
prompt["78"]["inputs"]["steps"] = total_steps
prompt["78"]["inputs"]["start_at_step"] = total_steps // 2
prompt["78"]["inputs"]["end_at_step"] = total_steps

# Resolution and frames
prompt["74"]["inputs"]["width"] = 640
prompt["74"]["inputs"]["height"] = 640
prompt["74"]["inputs"]["length"] = 81

# ComfyUI'ye gönder
url = "http://127.0.0.1:8188/prompt"
p = {"prompt": prompt, "client_id": "test123"}
data = json.dumps(p).encode('utf-8')

print("🔍 Sending prompt to ComfyUI...")
print(f"📋 Prompt nodes: {list(prompt.keys())}")

req = urllib.request.Request(url, data=data)
try:
    response = urllib.request.urlopen(req).read()
    result = json.loads(response)
    print(f"✅ SUCCESS: {result}")
except urllib.error.HTTPError as e:
    error_body = e.read().decode('utf-8')
    print(f"❌ ERROR {e.code}: {e.reason}")
    print(f"📄 Error Details:\n{error_body}")
except Exception as e:
    print(f"❌ EXCEPTION: {e}")
