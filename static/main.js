// static/main.js
// Robust MediaPipe JS + fallback camera logic.
// Handles upload (server measurement), client-side live pose rep counting,
// history display (server-side SQLite), and Web Speech voice control.

let camera = null;
let pose = null;
let videoElement = null;
let canvasElement = null;
let canvasCtx = null;
let repState = { state: "UP", count: 0, angleBuf: [], frameSinceTransition: 0 };
let smoothing = 4;
let minTimeFrames = 4;
let recognition = null;
let voiceEnabled = false;

window.addEventListener('DOMContentLoaded', () => {
  // Upload UI elements
  const fileInput = document.getElementById('file');
  const uploadBtn = document.getElementById('uploadBtn');
  const useHeight = document.getElementById('useHeight');
  const heightValue = document.getElementById('heightValue');
  const uploadStatus = document.getElementById('uploadStatus');
  const uploadResult = document.getElementById('uploadResult');
  const u_waist_px = document.getElementById('u_waist_px');
  const u_waist_cm = document.getElementById('u_waist_cm');
  const debugImg = document.getElementById('debug-img');
  const createUserBtn = document.getElementById('createUserBtn');
  const loginBtn = document.getElementById('loginBtn');
  const logoutBtn = document.getElementById('logoutBtn');
  const usernameInput = document.getElementById('usernameInput');
  const apiTokenInput = document.getElementById('apiToken');
  const copyTokenBtn = document.getElementById('copyTokenBtn');

  // Token management functions
  function setToken(token) {
    if (token) {
      apiTokenInput.value = token;
      localStorage.setItem("ai_fitness_token", token);
    } else {
      apiTokenInput.value = "";
      localStorage.removeItem("ai_fitness_token");
    }
  }

  function getToken() {
    return apiTokenInput.value || localStorage.getItem("ai_fitness_token") || "";
  }

  function ensureToken() {
    const token = getToken();
    if (!token) {
      throw new Error("Missing API token. Create a user first.");
    }
    return token;
  }

  // Fetch helper that automatically adds X-API-KEY header
  async function fetchWithToken(url, opts = {}) {
    const token = getToken();
    const headers = new Headers(opts.headers || {});
    if (token) {
      headers.set("X-API-KEY", token);
    }
    return fetch(url, { ...opts, headers });
  }

  // Alias for backward compatibility
  const authedFetch = fetchWithToken;

  // Create/Get Token button handler
  createUserBtn.addEventListener('click', async () => {
    const uname = (usernameInput.value || "").trim();
    if (!uname) {
      alert("Enter a username");
      return;
    }

    createUserBtn.disabled = true;
    createUserBtn.textContent = "Creating...";
    
    try {
      const form = new FormData();
      form.append("username", uname);

      const resp = await fetch("/api/users", {
        method: "POST",
        body: form
      });

      if (!resp.ok) {
        const errorText = await resp.text();
        alert(`Error: ${resp.status} ${resp.statusText}\n\n${errorText}\n\nPlease check server logs if this persists.`);
        return;
      }

      const data = await resp.json();
      if (data.token) {
        setToken(data.token);
        alert("User created. Token saved.");
        await loadHistory();
      } else {
        alert("Response missing token field.");
      }
    } catch (err) {
      alert("Network error: " + err.message);
    } finally {
      createUserBtn.disabled = false;
      createUserBtn.textContent = "Create / Get Token";
    }
  });

  // Login button handler (same as create, but also fetches history)
  loginBtn.addEventListener('click', async () => {
    const uname = (usernameInput.value || "").trim();
    if (!uname) {
      alert("Enter a username");
      return;
    }

    loginBtn.disabled = true;
    loginBtn.textContent = "Logging in...";
    
    try {
      const form = new FormData();
      form.append("username", uname);

      const resp = await fetch("/api/users", {
        method: "POST",
        body: form
      });

      if (!resp.ok) {
        const errorText = await resp.text();
        alert(`Error: ${resp.status} ${resp.statusText}\n\n${errorText}\n\nPlease check server logs if this persists.`);
        return;
      }

      const data = await resp.json();
      if (data.token) {
        setToken(data.token);
        // Automatically fetch history after login
        await loadHistory();
        alert("Logged in successfully!");
      } else {
        alert("Response missing token field.");
      }
    } catch (err) {
      alert("Network error: " + err.message);
    } finally {
      loginBtn.disabled = false;
      loginBtn.textContent = "Login";
    }
  });

  // Logout button handler
  logoutBtn.addEventListener('click', () => {
    setToken("");
    historyBody.innerHTML = "";
    historyStatus.textContent = "Logged out. Create a user to load history.";
    alert("Logged out. Token cleared.");
  });

  // Copy token button handler
  copyTokenBtn.addEventListener("click", async () => {
    const token = getToken();
    if (!token) {
      alert("No token to copy.");
      return;
    }
    try {
      await navigator.clipboard.writeText(token);
      alert("Token copied to clipboard!");
    } catch (err) {
      alert("Failed to copy token: " + err.message);
    }
  });

    
  

  uploadBtn.addEventListener('click', async () => {
    uploadStatus.textContent = "";
    uploadResult.style.display = "none";
    if (!fileInput.files.length) { uploadStatus.textContent = "Please select an image"; return; }
    const file = fileInput.files[0];
    const form = new FormData();
    form.append('file', file, file.name);
    form.append('use_height', useHeight.checked ? "true" : "false");
    form.append('height_cm', heightValue.value);

    uploadBtn.disabled = true; uploadBtn.textContent = "Uploading...";
    try {
      const resp = await fetchWithToken('/api/upload', { method: 'POST', body: form });
      if (resp.status === 401) {
        setToken("");
        alert("Authentication failed. Please login again.");
        return;
      }
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`Server error (${resp.status}): ${text || 'Unknown error'}`);
      }
      const j = await resp.json();
      u_waist_px.textContent = j.waist_px !== null ? j.waist_px : 'N/A';
      u_waist_cm.textContent = j.waist_cm !== null ? j.waist_cm.toFixed(1) + ' cm' : 'N/A';
      if (j.debug_png_b64) debugImg.src = 'data:image/png;base64,' + j.debug_png_b64;
      uploadResult.style.display = "block";
      // refresh history
      await loadHistory();
    } catch (err) {
      uploadStatus.textContent = "Error: " + (err.message || err);
    } finally {
      uploadBtn.disabled = false; uploadBtn.textContent = "Upload and Analyze";
    }
  });

  // Live Pose UI elements
  const startBtn = document.getElementById('startBtn');
  const stopBtn = document.getElementById('stopBtn');
  const resetBtn = document.getElementById('resetBtn');
  const snapshotBtn = document.getElementById('snapshotBtn');
  const repCountEl = document.getElementById('rep-count');
  const formFeedback = document.getElementById('form-feedback');
  const upAngleInput = document.getElementById('upAngle');
  const downAngleInput = document.getElementById('downAngle');
  const voiceToggle = document.getElementById('voiceToggle');

  videoElement = document.getElementById('input_video');
  canvasElement = document.getElementById('overlay');
  canvasCtx = canvasElement.getContext('2d');

  function resetCounter() {
    repState = { state: "UP", count: 0, angleBuf: [], frameSinceTransition: 0 };
    repCountEl.textContent = '0';
    formFeedback.textContent = '';
  }

  function smoothAngle(angle) {
    const buf = repState.angleBuf;
    buf.push(angle);
    if (buf.length > smoothing) buf.shift();
    const sum = buf.reduce((a,b)=>a+b,0);
    return sum / buf.length;
  }

  // angle between 3 points (landmarks have x,y in pixels)
  function angleBetween(a, b, c) {
    const va = [a.x - b.x, a.y - b.y];
    const vc = [c.x - b.x, c.y - b.y];
    const dot = va[0]*vc[0] + va[1]*vc[1];
    const mag = Math.sqrt(va[0]*va[0] + va[1]*va[1]) * Math.sqrt(vc[0]*vc[0] + vc[1]*vc[1]);
    if (mag === 0) return 0;
    let cosang = dot / mag;
    if (cosang > 1) cosang = 1;
    if (cosang < -1) cosang = -1;
    return Math.acos(cosang) * 180 / Math.PI;
  }

  function updateRepCounter(angle) {
    const upAngle = parseFloat(upAngleInput.value) || 150;
    const downAngle = parseFloat(downAngleInput.value) || 70;
    const sm = smoothAngle(angle);
    repState.frameSinceTransition++;
    if (repState.state === "UP") {
      if (sm < downAngle && repState.frameSinceTransition >= minTimeFrames) {
        repState.state = "DOWN";
        repState.frameSinceTransition = 0;
      }
    } else if (repState.state === "DOWN") {
      if (sm > upAngle && repState.frameSinceTransition >= minTimeFrames) {
        repState.state = "UP";
        repState.count += 1;
        repState.frameSinceTransition = 0;
        repCountEl.textContent = String(repState.count);
      }
    }
  }

  function drawLandmarksAndConnect(landmarks, ctx) {
    ctx.save();
    ctx.clearRect(0,0,canvasElement.width, canvasElement.height);
    try { ctx.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height); } catch(e){}
    ctx.strokeStyle = "rgba(0,255,0,0.8)";
    ctx.lineWidth = 2;
    for (const lm of landmarks) {
      ctx.beginPath();
      ctx.arc(lm.x * canvasElement.width, lm.y * canvasElement.height, 4, 0, 2*Math.PI);
      ctx.fillStyle = "rgba(255,0,0,0.9)"; ctx.fill();
    }
    if (landmarks[12] && landmarks[14]) {
      ctx.beginPath();
      ctx.moveTo(landmarks[12].x * canvasElement.width, landmarks[12].y * canvasElement.height);
      ctx.lineTo(landmarks[14].x * canvasElement.width, landmarks[14].y * canvasElement.height);
      ctx.stroke();
    }
    if (landmarks[14] && landmarks[16]) {
      ctx.beginPath();
      ctx.moveTo(landmarks[14].x * canvasElement.width, landmarks[14].y * canvasElement.height);
      ctx.lineTo(landmarks[16].x * canvasElement.width, landmarks[16].y * canvasElement.height);
      ctx.stroke();
    }
    ctx.restore();
  }

  async function onResults(results) {
    if (!results || !results.poseLandmarks) return;
    const lm = results.poseLandmarks.map(l => ({x: l.x, y: l.y, z: l.z, visibility: l.visibility}));
    drawLandmarksAndConnect(lm, canvasCtx);
    if (lm[12] && lm[14] && lm[16]) {
      const sh = {x: lm[12].x * canvasElement.width, y: lm[12].y * canvasElement.height};
      const el = {x: lm[14].x * canvasElement.width, y: lm[14].y * canvasElement.height};
      const wr = {x: lm[16].x * canvasElement.width, y: lm[16].y * canvasElement.height};
      const ang = angleBetween(sh, el, wr);
      updateRepCounter(ang);
      if (ang < 50) { formFeedback.textContent = "Good curl depth"; formFeedback.style.color = "green"; }
      else if (ang > 140) { formFeedback.textContent = "Extend arm"; formFeedback.style.color = "darkorange"; }
      else { formFeedback.textContent = ""; }
    }
  }

  // ---------- Robust MediaPipe initialization + camera start/stop ----------
  function getPoseClass() {
    // MediaPipe Pose 0.5 from CDN typically exposes it as window.Pose.Pose
    // Check all possible locations
    if (typeof window !== 'undefined') {
      // Check window.Pose.Pose (most common for CDN version 0.5)
      if (window.Pose && window.Pose.Pose && typeof window.Pose.Pose === 'function') {
        return window.Pose.Pose;
      }
      // Check window.Pose as direct constructor
      if (window.Pose && typeof window.Pose === 'function') {
        return window.Pose;
      }
      // Check mpPose namespace
      if (window.mpPose && window.mpPose.Pose && typeof window.mpPose.Pose === 'function') {
        return window.mpPose.Pose;
      }
      // Check for MediaPipeSolutions namespace (some versions)
      if (window.MediaPipeSolutions && window.MediaPipeSolutions.Pose) {
        return window.MediaPipeSolutions.Pose;
      }
    }
    // Check global scope (non-window) - for strict mode or module contexts
    try {
      if (typeof Pose !== 'undefined') {
        if (Pose.Pose && typeof Pose.Pose === 'function') {
          return Pose.Pose;
        }
        if (typeof Pose === 'function') {
          return Pose;
        }
      }
      if (typeof mpPose !== 'undefined' && mpPose.Pose && typeof mpPose.Pose === 'function') {
        return mpPose.Pose;
      }
    } catch (e) {
      // Ignore reference errors in strict mode
    }
    return null;
  }

  function waitForMediaPipe(maxAttempts = 50, interval = 100) {
    return new Promise((resolve, reject) => {
      let attempts = 0;
      const checkInterval = setInterval(() => {
        attempts++;
        const PoseClass = getPoseClass();
        if (PoseClass) {
          clearInterval(checkInterval);
          resolve(PoseClass);
        } else if (attempts >= maxAttempts) {
          clearInterval(checkInterval);
          // Log what we found for debugging
          const debugInfo = {
            'window.Pose': typeof window?.Pose,
            'window.mpPose': typeof window?.mpPose,
            'window keys with pose': Object.keys(window || {}).filter(k => k.toLowerCase().includes('pose') || k.toLowerCase().includes('media'))
          };
          console.error("MediaPipe not found. Debug info:", debugInfo);
          reject(new Error("MediaPipe Pose library failed to load after " + (maxAttempts * interval) + "ms. Check console for debug info."));
        }
      }, interval);
    });
  }

  async function initPose() {
    try {
      // Wait for MediaPipe to be available
      const PoseClass = await waitForMediaPipe();
      console.log("MediaPipe Pose class found, initializing...");
      
      pose = new PoseClass({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`
      });
      pose.setOptions({
        modelComplexity: 1,
        smoothLandmarks: true,
        enableSegmentation: false,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5
      });
      pose.onResults(onResults);
      console.log("MediaPipe Pose initialized successfully");
    } catch (err) {
      console.error("Failed to init MediaPipe Pose:", err);
      console.error("Debug info - Available globals:", {
        'window.Pose': typeof window?.Pose,
        'window.mpPose': typeof window?.mpPose,
        'Pose (global)': typeof Pose,
        'mpPose (global)': typeof mpPose,
        'window keys': Object.keys(window).filter(k => k.toLowerCase().includes('pose') || k.toLowerCase().includes('media'))
      });
      alert("MediaPipe Pose init failed: " + err.message + "\n\nCheck browser console for details.");
    }
  }

  function ensureCanvasMatchesVideo() {
    const vw = videoElement.videoWidth || 640;
    const vh = videoElement.videoHeight || 480;
    if (canvasElement.width !== vw || canvasElement.height !== vh) {
      canvasElement.width = vw; canvasElement.height = vh;
    }
  }

  async function startCamera() {
    if (camera) return;
    if (!pose) {
      await initPose();
      if (!pose) {
        formFeedback.textContent = "Failed to initialize MediaPipe Pose";
        formFeedback.style.color = "darkred";
        return;
      }
    }
    try {
      const CameraCtor = window.Camera;
      if (typeof CameraCtor !== "undefined") {
        camera = new CameraCtor(videoElement, {
          onFrame: async () => {
            try { ensureCanvasMatchesVideo(); await pose.send({ image: videoElement }); } catch(e){ console.error("pose.send error:", e); }
          },
          width: 640, height: 480
        });
        await camera.start();
        console.log("Camera started via MediaPipe Camera helper");
      } else {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
        videoElement.srcObject = stream;
        await videoElement.play();
        ensureCanvasMatchesVideo();
        let stopped = false;
        camera = { stop: () => { stopped = true; stream.getTracks().forEach(t => t.stop()); videoElement.pause(); videoElement.srcObject = null; } };
        async function frameLoop() { if (stopped) return; try { await pose.send({ image: videoElement }); } catch(e){ console.error("pose.send fallback error:", e);} requestAnimationFrame(frameLoop); }
        requestAnimationFrame(frameLoop);
        console.log("Camera started via getUserMedia fallback");
      }
      startBtn.disabled = true; stopBtn.disabled = false; snapshotBtn.disabled = false; formFeedback.textContent = "";
    } catch (err) {
      console.error("startCamera failed:", err);
      formFeedback.textContent = "Could not start camera: " + (err.message || err); formFeedback.style.color = "darkred";
      try { if (camera && camera.stop) camera.stop(); } catch (_) {}
      camera = null; startBtn.disabled = false; stopBtn.disabled = true; snapshotBtn.disabled = true;
    }
  }

  function stopCamera() {
    try {
      if (!camera) return;
      if (camera.stop) camera.stop();
      camera = null;
      canvasCtx.clearRect(0,0,canvasElement.width, canvasElement.height);
      startBtn.disabled = false; stopBtn.disabled = true; snapshotBtn.disabled = true; formFeedback.textContent = "";
      console.log("Camera stopped");
    } catch (err) { console.error("stopCamera error:", err); }
  }
  // ---------- end camera block ----------

  startBtn.addEventListener('click', () => startCamera());
  stopBtn.addEventListener('click', () => stopCamera());
  resetBtn.addEventListener('click', () => resetCounter());

  // snapshot current canvas and send to server (reuses /api/upload)
  snapshotBtn.addEventListener('click', async () => {
    await doSnapshotUpload();
  });

  async function doSnapshotUpload() {
    const dataUrl = canvasElement.toDataURL('image/png');
    const blob = await (await fetch(dataUrl)).blob();
    const f = new File([blob], 'snapshot.png', { type: 'image/png' });
    const form = new FormData();
    form.append('file', f);
    form.append('use_height', "false");
    try {
      snapshotBtn.disabled = true; snapshotBtn.textContent = "Sending...";
      const resp = await fetchWithToken('/api/upload', { method: 'POST', body: form });
      if (resp.status === 401) {
        setToken("");
        alert("Authentication failed. Please login again.");
        return;
      }
      if (!resp.ok) {
        const errorText = await resp.text();
        throw new Error(`Server error (${resp.status}): ${errorText || 'Unknown error'}`);
      }
      const j = await resp.json();
      alert('Snapshot saved. Waist px: ' + (j.waist_px !== null ? j.waist_px : 'N/A'));
      await loadHistory();
    } catch (err) {
      alert('Snapshot upload failed: ' + err.message);
    } finally {
      snapshotBtn.disabled = false; snapshotBtn.textContent = "Snapshot → Server";
    }
  }

  // ------------------- History UI -------------------
  const historyBody = document.getElementById('historyBody');
  const historyStatus = document.getElementById('historyStatus');

  async function loadHistory() {
    const token = getToken();
    if (!token) {
      historyBody.innerHTML = "";
      historyStatus.textContent = "Create a user to load history.";
      return;
    }
    try {
      historyStatus.textContent = "Loading...";
      const resp = await fetchWithToken('/api/history');
      
      if (resp.status === 401) {
        // Token invalid - clear it and notify user
        setToken("");
        historyBody.innerHTML = "";
        historyStatus.textContent = "Authentication failed. Please login again.";
        alert("Session expired. Please login again.");
        return;
      }
      
      if (!resp.ok) {
        const errorText = await resp.text();
        historyStatus.textContent = `Failed to load history: ${resp.status} ${resp.statusText}`;
        console.error("History load error:", errorText);
        return;
      }
      
      const json = await resp.json();
      historyBody.innerHTML = "";
      for (const item of json) {
        const tr = document.createElement('tr');
        const previewTd = document.createElement('td');
        const img = document.createElement('img');
        img.src = '/uploads/' + item.filename;
        img.style.width = '120px';
        previewTd.appendChild(img);
        const fnameTd = document.createElement('td'); fnameTd.textContent = item.filename;
        const tsTd = document.createElement('td'); tsTd.textContent = item.timestamp;
        const pxTd = document.createElement('td'); pxTd.textContent = item.waist_px !== null ? item.waist_px : '';
        const cmTd = document.createElement('td'); cmTd.textContent = item.waist_cm !== null ? item.waist_cm.toFixed(1) : '';
        const actionTd = document.createElement('td');
        const delBtn = document.createElement('button'); delBtn.textContent = 'Delete';
        delBtn.addEventListener('click', async () => {
          if (!confirm('Delete this record?')) return;
          try {
            const dresp = await fetchWithToken('/api/history/' + item.id, { method: 'DELETE' });
            if (dresp.ok) { 
              await loadHistory(); 
            } else {
              const errorText = await dresp.text();
              alert(`Delete failed: ${dresp.status} ${dresp.statusText}\n\n${errorText}`);
            }
          } catch (err) {
            alert('Delete error: ' + err.message);
          }
        });
        actionTd.appendChild(delBtn);
        tr.appendChild(previewTd); tr.appendChild(fnameTd); tr.appendChild(tsTd); tr.appendChild(pxTd); tr.appendChild(cmTd); tr.appendChild(actionTd);
        historyBody.appendChild(tr);
      }
      historyStatus.textContent = "";
    } catch (e) {
      console.error("loadHistory error", e);
      historyStatus.textContent = "Failed to load history: " + e.message;
    }
  }

  // Auto-load token from localStorage on page load and fetch history
  const savedToken = localStorage.getItem("ai_fitness_token");
  if (savedToken) {
    setToken(savedToken);
    loadHistory();
  }

  // ------------------- Voice control -------------------
  function setupVoice() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Web Speech API not supported by this browser. Use Chrome/Edge.");
      return;
    }
    recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.continuous = true;

    recognition.onresult = (event) => {
      const transcript = event.results[event.results.length - 1][0].transcript.trim().toLowerCase();
      console.log("Voice heard:", transcript);
      handleVoiceCommand(transcript);
    };

    recognition.onstart = () => { 
      console.log("Voice recognition started"); 
      voiceToggle.classList.add('active'); 
      voiceEnabled = true; 
    };
    recognition.onend = () => { 
      console.log("Voice recognition ended"); 
      voiceToggle.classList.remove('active'); 
      voiceEnabled = false; 
    };
    recognition.onerror = (e) => { 
      console.error("Voice error", e); 
      voiceToggle.classList.remove('active'); 
      voiceEnabled = false;
      alert("Voice error: " + e.error); 
    };
  }

  function handleVoiceCommand(text) {
    // Camera controls
    if (text.includes("start camera") || (text.includes("start") && text.includes("camera"))) {
      startCamera();
    } else if (text.includes("stop camera") || (text.includes("stop") && text.includes("camera"))) {
      stopCamera();
    } 
    // Snapshot controls
    else if (text.includes("take snapshot") || text.includes("take a snapshot") || text.includes("snapshot") || text.includes("save snapshot")) {
      doSnapshotUpload();
    }
    // Rep counter controls
    else if (text.includes("reset counter") || text.includes("reset reps") || text.includes("reset rep") || 
             text.includes("zero counter") || text.includes("zero reps") || text.includes("clear counter") ||
             text.includes("clear reps") || (text.includes("reset") && (text.includes("count") || text.includes("rep")))) {
      resetCounter();
      formFeedback.textContent = "Rep counter reset";
      formFeedback.style.color = "green";
      setTimeout(() => { formFeedback.textContent = ""; }, 2000);
    }
    // Unrecognized command
    else {
      console.log("Unrecognized voice command:", text);
    }
  }

  voiceToggle.addEventListener('click', () => {
    if (!recognition) setupVoice();
    if (!recognition) return;
    if (!voiceEnabled) {
      try {
        recognition.start();
      } catch (e) { console.warn("recognition.start error", e); }
    } else {
      recognition.stop();
    }
  });

  // end DOMContentLoaded
});
