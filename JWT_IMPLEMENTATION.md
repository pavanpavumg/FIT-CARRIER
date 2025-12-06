# JWT Authentication Implementation Guide

## Overview
This document describes the JWT (JSON Web Token) authentication system implemented for the Flask Fitness App.

## Files Created/Modified

### Backend Files
1. **app_flask.py** - Main Flask application with JWT authentication
   - Uses `flask-jwt-extended` for JWT token management
   - Password hashing with `werkzeug.security`
   - Protected routes using `@jwt_required()` decorator
   - Database schema updated to include `password_hash` field

### Frontend Files
1. **templates/login.html** - Login page with cyberpunk styling
   - Form-based login with username/password
   - Registration link (calls `/api/register`)
   - Error handling and loading states
   - Auto-redirects to dashboard on successful login

2. **static/main_jwt.js** - Updated JavaScript for JWT authentication
   - Uses `Authorization: Bearer <token>` header instead of `X-API-KEY`
   - Token stored in localStorage as `jwt_token`
   - Auto-redirects to login if token is missing or expired
   - Logout functionality

3. **templates/index.html** - Updated dashboard
   - Added prominent logout button (neon red style) in header
   - Changed script reference to `main_jwt.js`

## API Endpoints

### Public Endpoints
- `GET /login` - Login page
- `POST /api/login` - Login endpoint
  - Request: `{"username": "...", "password": "..."}`
  - Response: `{"access_token": "..."}`
- `POST /api/register` - Registration endpoint
  - Request: `{"username": "...", "password": "..."}`
  - Response: `{"access_token": "...", "message": "User created successfully"}`

### Protected Endpoints (require JWT)
- `GET /` - Dashboard (protected)
- `POST /api/upload` - Upload image
- `GET /api/history` - Get measurement history
- `DELETE /api/history/<id>` - Delete history item
- `GET /uploads/<filename>` - Serve uploaded files

## Authentication Flow

1. **Login Process:**
   - User enters username/password on `/login`
   - JavaScript sends POST to `/api/login`
   - Backend validates credentials against database
   - If valid, returns JWT token
   - Frontend saves token to `localStorage.jwt_token`
   - Redirects to dashboard (`/`)

2. **Protected Route Access:**
   - Dashboard checks for `jwt_token` in localStorage
   - If missing, redirects to `/login`
   - All API calls include `Authorization: Bearer <token>` header
   - Backend validates token using `@jwt_required()` decorator

3. **Logout Process:**
   - User clicks logout button
   - JavaScript removes `jwt_token` from localStorage
   - Redirects to `/login`

## Database Schema Changes

The users table now includes a password hash:
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);
```

**Note:** Existing users from the old token-based system will need to be migrated or recreated.

## Installation

1. Install dependencies:
```bash
pip install -r requirements_flask.txt
```

2. Set JWT secret key (recommended for production):
```bash
export JWT_SECRET_KEY="your-secret-key-here"
```

3. Run the Flask app:
```bash
python app_flask.py
```

## JavaScript Functions

### Token Management
- `getJWTToken()` - Retrieves JWT token from localStorage
- `fetchWithToken(url, opts)` - Wrapper that automatically adds `Authorization: Bearer` header
  - Handles 401 responses by clearing token and redirecting to login

### Logout
- Logout button handler removes token and redirects to login page

## Styling

The login page uses the existing cyberpunk/dark mode CSS theme with:
- Neon cyan/purple gradients
- Animated background effects
- Smooth transitions and hover effects
- Error message display with shake animation

The logout button is styled as a neon red button in the dashboard header with hover effects.

## Security Notes

1. **Password Hashing:** Passwords are hashed using Werkzeug's `generate_password_hash()` before storage
2. **JWT Expiration:** Tokens expire after 24 hours (configurable in `app.config['JWT_ACCESS_TOKEN_EXPIRES']`)
3. **Secret Key:** Change `JWT_SECRET_KEY` in production (use environment variable)
4. **HTTPS:** Use HTTPS in production to protect tokens in transit

## Migration from FastAPI to Flask

If migrating from the existing FastAPI app:
1. Backup existing database
2. Run migration script to add password_hash column (or recreate users)
3. Update frontend to use JWT tokens instead of API keys
4. Test all protected endpoints

## Testing

1. **Register a new user:**
   - Go to `/login`
   - Enter username and password
   - Click "Register here" link
   - Should receive token and redirect to dashboard

2. **Login:**
   - Go to `/login`
   - Enter credentials
   - Should receive token and redirect to dashboard

3. **Access protected routes:**
   - Try accessing `/` without token - should redirect to login
   - After login, should access dashboard successfully

4. **Logout:**
   - Click logout button
   - Should clear token and redirect to login
   - Trying to access dashboard should redirect back to login

5. **Token expiration:**
   - Wait for token to expire (or manually clear it)
   - API calls should return 401 and redirect to login

