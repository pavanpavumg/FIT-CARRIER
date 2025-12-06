# How to Run the Flask Fitness App

## Quick Start (Windows PowerShell)

### Step 1: Activate Virtual Environment
```powershell
.\venv\Scripts\Activate.ps1
```

If you get an execution policy error, run this first:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Step 2: Install Dependencies (if not already installed)
```powershell
pip install -r requirements_flask.txt
```

### Step 3: Run the Flask App
```powershell
python app_flask.py
```

### Step 4: Access the Application
- Open your browser and go to: **http://127.0.0.1:8000/login**
- You should see the login page

## Alternative: Using Command Prompt (CMD)

### Step 1: Activate Virtual Environment
```cmd
venv\Scripts\activate.bat
```

### Step 2: Install Dependencies
```cmd
pip install -r requirements_flask.txt
```

### Step 3: Run the Flask App
```cmd
python app_flask.py
```

## What You Should See

When the app starts successfully, you'll see:
```
 * Serving Flask app 'app_flask'
 * Debug mode: on
WARNING: This is a development server...
 * Running on http://127.0.0.1:8000
Press CTRL+C to quit
```

## First Time Setup

1. **Register a new user:**
   - Go to http://127.0.0.1:8000/login
   - Enter a username and password
   - Click "Register here" link
   - You'll be automatically logged in and redirected to the dashboard

2. **Or login with existing credentials:**
   - Enter username and password
   - Click "Login" button

## Troubleshooting

### Issue: "python is not recognized"
- Make sure the virtual environment is activated
- Or use: `venv\Scripts\python.exe app_flask.py`

### Issue: "ModuleNotFoundError: No module named 'flask'"
- Install dependencies: `pip install -r requirements_flask.txt`

### Issue: "Execution Policy" error in PowerShell
- Run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- Then try activating the venv again

### Issue: Port 8000 already in use
- Change the port in `app_flask.py` (last line):
  ```python
  app.run(host="127.0.0.1", port=8001, debug=True)
  ```

## Stopping the Server

Press `CTRL+C` in the terminal to stop the Flask server.

