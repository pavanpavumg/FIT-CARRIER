# QA Checklist - Login UI + Logout Functionality

## Manual Testing Steps

### 1. Create/Get Token
- [ ] Enter a username in the `usernameInput` field
- [ ] Click "Create / Get Token" button
- [ ] Verify token appears in `#apiToken` input field
- [ ] Verify token is stored in localStorage under key `ai_fitness_token`
- [ ] Verify button shows "Creating..." while request is in-flight
- [ ] Verify button is disabled during request
- [ ] Test with same username again - should return existing token (idempotent)

### 2. Login
- [ ] Enter a username (can be existing or new)
- [ ] Click "Login" button
- [ ] Verify token appears in `#apiToken` input field
- [ ] Verify token is stored in localStorage
- [ ] Verify history table automatically populates after login
- [ ] Verify button shows "Logging in..." while request is in-flight
- [ ] Verify button is disabled during request

### 3. Auto-load on Page Load
- [ ] Close browser tab/window
- [ ] Reopen the application
- [ ] Verify token from localStorage automatically populates `#apiToken` field
- [ ] Verify history table automatically loads on page load

### 4. Upload with Token
- [ ] Ensure token is set (via Create/Get Token or Login)
- [ ] Select an image file
- [ ] Click "Upload and Analyze"
- [ ] Verify request includes `X-API-KEY` header automatically
- [ ] Verify upload succeeds and returns waist measurements
- [ ] Verify history table refreshes after upload

### 5. History Fetch
- [ ] With valid token, verify `/api/history` returns 200
- [ ] Verify history table displays all records correctly
- [ ] Verify preview images load correctly
- [ ] Verify delete button works for each record

### 6. Logout
- [ ] Click "Logout" button
- [ ] Verify token is cleared from `#apiToken` input
- [ ] Verify token is removed from localStorage
- [ ] Verify history table is cleared
- [ ] Verify protected calls (upload, history) return 401 after logout

### 7. Copy Token
- [ ] With token set, click "Copy" button
- [ ] Verify token is copied to clipboard
- [ ] Verify confirmation alert appears
- [ ] Paste clipboard and verify token matches

### 8. Error Handling

#### Server Errors (4xx/5xx)
- [ ] Test with invalid username (if backend validates)
- [ ] Verify raw server response text is shown in alert
- [ ] Verify error message includes status code and response text
- [ ] Test with corrupted DB scenario (if possible)
- [ ] Verify helpful message about checking server logs

#### Authentication Errors (401)
- [ ] Manually clear token from localStorage
- [ ] Try to upload an image
- [ ] Verify 401 response clears token automatically
- [ ] Verify user is notified to login again
- [ ] Test history fetch with invalid token
- [ ] Verify 401 response clears token and shows message

### 9. Logo Image
- [ ] Verify logo image loads from `/mnt/data/AI_fitness_analysis1[1] (1).pdf`
- [ ] If logo fails to load, verify fallback placeholder appears
- [ ] Verify logo doesn't break page layout

### 10. UI Layout
- [ ] Verify Account card appears near top of page (above upload section)
- [ ] Verify all buttons are visible and properly aligned
- [ ] Verify responsive layout works on different screen sizes
- [ ] Verify token input field is readonly and properly styled

## Edge Cases

- [ ] Empty username submission - should show alert
- [ ] Network failure during create/login - should show error
- [ ] Multiple rapid clicks on buttons - should prevent duplicate requests
- [ ] Token expiration scenario (if applicable)
- [ ] Very long token strings - verify UI doesn't break

## Browser Compatibility

- [ ] Test in Chrome/Edge (for Clipboard API)
- [ ] Test in Firefox
- [ ] Test localStorage persistence across sessions
- [ ] Test with localStorage disabled (should still work, just no persistence)

