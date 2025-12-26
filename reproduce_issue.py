import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_endpoint(name, method, url, data=None, files=None, headers=None):
    print(f"Testing {name} ({method} {url})...")
    try:
        if method == "POST":
            if files:
                response = requests.post(url, files=files, data=data, headers=headers)
            else:
                response = requests.post(url, json=data, headers=headers)
        elif method == "GET":
            response = requests.get(url, params=data, headers=headers)
        
        print(f"Status: {response.status_code}")
        if response.status_code == 422:
            print("!!! FOUND 422 !!!")
            print("Response:", response.text)
        elif response.status_code != 200:
             print("Response:", response.text[:200]) # truncated
        print("-" * 20)
    except Exception as e:
        print(f"Failed to connect: {e}")

# 1. Weekly Report (Suspect)
test_endpoint(
    "Weekly Report (Valid)", 
    "POST", 
    f"{BASE_URL}/api/weekly_report", 
    data={"username": "testuser", "token": "testtoken"}
)

test_endpoint(
    "Weekly Report (Missing Token)", 
    "POST", 
    f"{BASE_URL}/api/weekly_report", 
    data={"username": "testuser"}
)

test_endpoint(
    "Weekly Report (Empty Body)", 
    "POST", 
    f"{BASE_URL}/api/weekly_report", 
    data={}
)

# 2. Users (Create)
test_endpoint(
    "Create User (JSON - potential 422 if Expecting Form)", 
    "POST", 
    f"{BASE_URL}/api/users", 
    data={"username": "testuser_json"} # sending json to form endpoint
)

test_endpoint(
    "Create User (Form - Correct)", 
    "POST", 
    f"{BASE_URL}/api/users", 
    data={"username": "testuser_form"},
    files={} # triggers multipart/form-data
)

# 3. Log Workout
test_endpoint(
    "Log Workout (Valid)", 
    "POST", 
    f"{BASE_URL}/api/log_workout", 
    data={"reps": 10, "workout_type": "squat"}
)

# 4. Upload (Empty)
test_endpoint(
    "Upload (No File)", 
    "POST", 
    f"{BASE_URL}/api/upload", 
    data={}
)
