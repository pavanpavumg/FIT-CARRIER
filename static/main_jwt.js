// static/main_jwt.js
// Improved and fixed version for your Flask + MediaPipe app.
// Replaces the previous static/main_jwt.js with more robust handling.

var camera = null;
var pose = null;
var videoElement = null;
var canvasElement = null;
var canvasCtx = null;
var repState = { state: "UP", count: 0, angleBuf: [], frameSinceTransition: 0 };
var smoothing = 4;
var minTimeFrames = 4;


function animateValue(obj, start, end, duration) {
  if (!obj) return;
  let startTimestamp = null;
  const step = (timestamp) => {
    if (!startTimestamp) startTimestamp = timestamp;
    const progress = Math.min((timestamp - startTimestamp) / duration, 1);
    obj.innerHTML = Math.floor(progress * (end - start) + start);
    if (progress < 1) {
      window.requestAnimationFrame(step);
    } else {
      obj.innerHTML = end; // Ensure final value is exact
    }
  };
  window.requestAnimationFrame(step);
}



// Voice Toggle UI (Global)


window.addEventListener('DOMContentLoaded', () => {
  // --- Helper for robust modal retrieval ---
  function safeGetModal(el, options = {}) {
    if (!el) return null;
    // Check if instance already exists
    let check = bootstrap.Modal.getInstance(el);
    if (check) return check;
    // Create new instance
    return new bootstrap.Modal(el, { backdrop: 'static', keyboard: true, ...options });
  }

  // Init Voice


  // Voice Toggle UI


  // --- Elements / auth ---
  const usernameInput = document.getElementById('usernameInput');

  const createUserBtn = document.getElementById('createUserBtn');
  const apiToken = document.getElementById('apiToken');
  const copyTokenBtn = document.getElementById('copyTokenBtn');
  const clearTokenBtn = document.getElementById('clearTokenBtn');
  const tutorialSearchInput = document.getElementById('tutorialSearchInput');
  const tutorialSearchBtn = document.getElementById('tutorialSearchBtn');

  // Upload elements
  const fileInput = document.getElementById('file');
  const uploadBtn = document.getElementById('uploadBtn');
  const useHeight = document.getElementById('useHeight');
  const heightValue = document.getElementById('heightValue');
  const ageValue = document.getElementById('ageValue');
  const uploadStatus = document.getElementById('uploadStatus');
  const uploadResult = document.getElementById('uploadResult');
  const u_waist_px = document.getElementById('u_waist_px');
  const u_waist_cm = document.getElementById('u_waist_cm');
  const debugImg = document.getElementById('debug-img');

  // Live pose controls
  const startBtn = document.getElementById('startBtn');
  const stopBtn = document.getElementById('stopBtn');
  const resetBtn = document.getElementById('resetBtn');
  const snapshotBtn = document.getElementById('snapshotBtn');
  const repCountEl = document.getElementById('rep-count');
  const repCountSideEl = document.getElementById('rep-count-side');
  const formFeedback = document.getElementById('form-feedback');
  const upAngleInput = document.getElementById('upAngle');
  const downAngleInput = document.getElementById('downAngle');


  // History & modals elements
  const historyBody = document.getElementById('historyBody');
  const historyStatus = document.getElementById('historyStatus');
  const historyCard = document.getElementById('historyCard');
  const loadHistoryBtn = document.getElementById('loadHistoryBtn');
  const workoutModal = document.getElementById('workoutModal');
  const modalWorkoutList = document.getElementById('modalWorkoutList');
  const closeWorkoutModal = document.getElementById('closeWorkoutModal');
  const tutorialModal = document.getElementById('tutorialModal');
  const tutorialTitle = document.getElementById('tutorialTitle');
  const tutorialFrame = document.getElementById('tutorialFrame');
  const tutorialLink = document.getElementById('tutorialLink');
  const closeTutorialModal = document.getElementById('closeTutorialModal');

  videoElement = document.getElementById('input_video');
  canvasElement = document.getElementById('overlay');
  canvasCtx = canvasElement ? canvasElement.getContext('2d') : null;

  // --- Auth Check ---
  // Improved: Resume from local storage or wait for user input
  let token = localStorage.getItem('ai_fitness_token') || localStorage.getItem('jwt_token') || '';

  if (apiToken) apiToken.value = token;

  if (typeof checkGamification === 'function') {
    checkGamification();
  }

  if (apiToken) {
    apiToken.addEventListener('input', () => {
      const v = apiToken.value.trim();
      if (v) localStorage.setItem('ai_fitness_token', v);
      else {
        localStorage.removeItem('ai_fitness_token');
        localStorage.removeItem('jwt_token');
      }
    });
  }

  if (clearTokenBtn && apiToken) {
    clearTokenBtn.addEventListener('click', () => {
      apiToken.value = '';
      localStorage.removeItem('ai_fitness_token');
      localStorage.removeItem('jwt_token');
      apiToken.focus();
    });
  }

  if (tutorialSearchBtn) tutorialSearchBtn.addEventListener('click', handleManualSearch);
  if (tutorialSearchInput) {
    tutorialSearchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); handleManualSearch(); }
    });
  }

  // --- Auth endpoints ---
  if (createUserBtn) {
    createUserBtn.addEventListener('click', async () => {
      const uname = (usernameInput?.value || "").trim();
      if (!uname) { alert("Enter a username"); return; }
      createUserBtn.disabled = true; createUserBtn.textContent = "Creating...";
      try {
        const form = new FormData(); form.append('username', uname);
        const resp = await fetch('/api/users', { method: 'POST', body: form });
        const text = await resp.text();

        if (resp.status === 409) {
          alert(`User ${uname} already exists! Please enter your existing API Key in the box.`);
          if (apiToken) {
            apiToken.value = '';
            apiToken.focus();
          }
          return;
        }

        if (!resp.ok) {
          const msg = text || `${resp.status} ${resp.statusText}`;
          alert('Create user failed: ' + msg);
          return;
        }
        const data = JSON.parse(text);
        if (data.token) {
          apiToken.value = data.token;
          localStorage.setItem('ai_fitness_token', data.token);
          // NEW: Use specific message if available
          alert(data.message || 'User token saved locally.');
          await loadHistory({ username: uname, token: data.token });
          // Ensure gamification stats update immediately
          if (window.fetchGamificationStats) {
            window.fetchGamificationStats();
          }
        } else {
          alert('Server response missing token');
        }
      } catch (e) {
        console.error('createUser error', e);
        alert('Create user network error: ' + e.message);
      } finally {
        createUserBtn.disabled = false; createUserBtn.textContent = 'Create / Get Token';
      }
    });
  }

  if (copyTokenBtn && apiToken) {
    copyTokenBtn.addEventListener('click', () => {
      apiToken.select();
      document.execCommand('copy');
      alert('Token copied to clipboard');
    });
  }

  // --- token helpers ---
  function getJWTToken() {
    const tokenInput = document.getElementById('apiToken');
    if (tokenInput && tokenInput.value) return tokenInput.value.trim();
    return localStorage.getItem('jwt_token') || localStorage.getItem('ai_fitness_token') || '';
  }

  async function fetchWithToken(url, opts = {}) {
    const token = getJWTToken();
    const headers = new Headers(opts.headers || {});
    if (token) {
      if (token.length > 40) headers.set('Authorization', `Bearer ${token}`);
      else headers.set('X-API-KEY', token);
    }
    const response = await fetch(url, { ...opts, headers });
    if (response.status === 401) {
      // clear stored token (non-destructive)
      localStorage.removeItem('jwt_token');
      // don't throw — let caller handle it
    }
    return response;
  }

  // --- Upload/Analyze ---
  if (uploadBtn) {
    uploadBtn.addEventListener('click', async () => {
      uploadStatus.textContent = '';
      if (!fileInput || !fileInput.files || !fileInput.files.length) {
        uploadStatus.textContent = 'Please select an image';
        return;
      }
      const file = fileInput.files[0];
      const form = new FormData();
      form.append('file', file, file.name);
      form.append('use_height', useHeight?.checked ? 'true' : 'false');
      if (heightValue?.value) form.append('height_cm', heightValue.value);
      if (ageValue?.value) form.append('age', ageValue.value);

      uploadBtn.disabled = true; uploadBtn.textContent = 'Uploading...';
      try {
        const resp = await fetchWithToken('/api/upload', { method: 'POST', body: form });
        const text = await resp.text();
        if (!resp.ok) throw new Error(text || `${resp.status} ${resp.statusText}`);
        const j = JSON.parse(text);
        u_waist_px && (u_waist_px.textContent = j.waist_px != null ? j.waist_px : 'N/A');
        u_waist_cm && (u_waist_cm.textContent = j.waist_cm != null ? j.waist_cm.toFixed(1) : 'N/A');

        // Optional body fat display
        if (j.body_fat_percentage != null) {
          const bf = document.getElementById('bodyFatDisplay');
          const bfSpan = document.getElementById('u_body_fat');
          if (bf) bf.style.display = 'block';
          if (bfSpan) bfSpan.textContent = j.body_fat_percentage.toFixed(1);
        } else {
          const bf = document.getElementById('bodyFatDisplay');
          if (bf) bf.style.display = 'none';
        }

        const methodEl = document.getElementById('method_used');
        if (methodEl) methodEl.textContent = j.method_used || 'Unknown';

        // Update Scan Quality Badge
        const qualBadge = document.getElementById('scan_quality_badge');
        const qualMsg = document.getElementById('scan_quality_msg');
        if (qualBadge && j.scan_quality) {
          qualBadge.textContent = j.scan_quality.score;
          qualBadge.className = 'badge'; // reset
          if (j.scan_quality.color === 'green') qualBadge.classList.add('bg-success');
          else if (j.scan_quality.color === 'yellow') qualBadge.classList.add('bg-warning', 'text-dark');
          else qualBadge.classList.add('bg-danger');

          if (qualMsg) qualMsg.textContent = j.scan_quality.message;
        } else if (qualBadge) {
          qualBadge.textContent = 'N/A';
          qualBadge.className = 'badge bg-secondary';
          if (qualMsg) qualMsg.textContent = '';
        }

        if (j.debug_png_b64 && debugImg) debugImg.src = 'data:image/png;base64,' + j.debug_png_b64;
        if (uploadResult) uploadResult.style.display = 'block';

        // Show recommended workouts if present
        if (j.workouts && Array.isArray(j.workouts) && j.workouts.length) {
          renderWorkoutCards(j.workouts);
        } else {
          hideWorkoutSection();
        }

        // refresh history (if user token exists)
        const uname = (usernameInput?.value || '').trim();
        const token = getJWTToken();
        if (uname && token) await loadHistory({ username: uname, token });

        // Check for warning status
        if (j.status === 'warning') {
          alert('Analysis Complete, but not saved to history: ' + (j.message || 'Suspicious variance detected.'));
          if (uploadStatus) {
            uploadStatus.textContent = 'Warning: ' + (j.message || 'Data not saved.');
            uploadStatus.style.color = 'orange';
            uploadStatus.textContent = 'Warning: ' + (j.message || 'Data not saved.');
            uploadStatus.style.color = 'orange';
          }
        }

        // Gamification Update
        if (j.streak_count !== undefined) {
          updateGamificationUI(j);
        }

      } catch (err) {
        console.error('upload error', err);
        uploadStatus.textContent = 'Error: ' + (err.message || err);
      } finally {
        uploadBtn.disabled = false; uploadBtn.textContent = 'Upload and Analyze';
      }
    });
  }

  // --- Rep counting utilities ---
  function resetCounter() {
    repState = { state: "UP", count: 0, angleBuf: [], frameSinceTransition: 0 };
    if (repCountEl) repCountEl.textContent = '0';
    if (repCountSideEl) repCountSideEl.textContent = '0';
    if (formFeedback) formFeedback.textContent = '';
  }

  function smoothAngle(angle) {
    const buf = repState.angleBuf;
    buf.push(angle);
    if (buf.length > smoothing) buf.shift();
    const sum = buf.reduce((a, b) => a + b, 0);
    return sum / buf.length;
  }

  function angleBetween(a, b, c) {
    const va = [a.x - b.x, a.y - b.y];
    const vc = [c.x - b.x, c.y - b.y];
    const dot = va[0] * vc[0] + va[1] * vc[1];
    const mag = Math.sqrt(va[0] * va[0] + va[1] * va[1]) * Math.sqrt(vc[0] * vc[0] + vc[1] * vc[1]);
    if (mag === 0) return 0;
    let cosang = dot / mag;
    cosang = Math.max(-1, Math.min(1, cosang));
    return Math.acos(cosang) * 180 / Math.PI;
  }

  function updateRepCounter(angle) {
    const upAngle = parseFloat(upAngleInput?.value) || 150;
    const downAngle = parseFloat(downAngleInput?.value) || 70;
    const sm = smoothAngle(angle);
    repState.frameSinceTransition++;
    if (repState.state === 'UP') {
      if (sm < downAngle && repState.frameSinceTransition >= minTimeFrames) {
        repState.state = 'DOWN'; repState.frameSinceTransition = 0;
        // update stage displays if present
        document.getElementById('stageVal') && (document.getElementById('stageVal').textContent = 'DOWN');
        document.getElementById('stageValSide') && (document.getElementById('stageValSide').textContent = 'DOWN');
      }
    } else {
      if (sm > upAngle && repState.frameSinceTransition >= minTimeFrames) {
        repState.state = 'UP'; repState.count += 1; repState.frameSinceTransition = 0;
        if (repCountEl) repCountEl.textContent = String(repState.count);
        if (repCountSideEl) repCountSideEl.textContent = String(repState.count);
        document.getElementById('stageVal') && (document.getElementById('stageVal').textContent = 'UP');
        document.getElementById('stageValSide') && (document.getElementById('stageValSide').textContent = 'UP');
      }
    }
  }

  function drawLandmarksAndConnect(landmarks, ctx) {
    if (!ctx || !canvasElement || !videoElement) return;
    ctx.save();
    ctx.clearRect(0, 0, canvasElement.width, canvasElement.height);
    try { ctx.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height); } catch (e) { }
    // Draw connections - Use Bright Green
    ctx.strokeStyle = "rgb(0, 255, 0)";
    ctx.lineWidth = 4;

    // Define standard Pose connections
    const connections = [
      [11, 12], [11, 13], [13, 15], [12, 14], [14, 16], // Upper body
      [11, 23], [12, 24], [23, 24],                     // Torso
      [23, 25], [25, 27], [24, 26], [26, 28]            // Legs
    ];

    ctx.beginPath();
    for (const [start, end] of connections) {
      if (landmarks[start] && landmarks[end] &&
        (landmarks[start].visibility || 1) > 0.3 && (landmarks[end].visibility || 1) > 0.3) {
        ctx.moveTo(landmarks[start].x * canvasElement.width, landmarks[start].y * canvasElement.height);
        ctx.lineTo(landmarks[end].x * canvasElement.width, landmarks[end].y * canvasElement.height);
      }
    }
    ctx.stroke();

    // Draw joints - Red with White border
    for (const lm of landmarks) {
      if ((lm.visibility || 1) < 0.3) continue;
      ctx.beginPath();
      ctx.arc(lm.x * canvasElement.width, lm.y * canvasElement.height, 4, 0, 2 * Math.PI);
      ctx.fillStyle = "rgb(255, 0, 0)";
      ctx.fill();
      ctx.strokeStyle = "white";
      ctx.lineWidth = 1;
      ctx.stroke();
    }
    ctx.restore();
  }

  async function onResults(results) {
    if (!results || !results.poseLandmarks) {
      console.log("Landmarks Detected: false");
      return;
    }
    console.log("Landmarks Detected: true");
    const lm = results.poseLandmarks.map(l => ({ x: l.x, y: l.y, z: l.z, visibility: l.visibility }));
    drawLandmarksAndConnect(lm, canvasCtx);
    // compute right elbow angle (shoulder 12, elbow 14, wrist 16)
    if (lm[12] && lm[14] && lm[16]) {
      const sh = { x: lm[12].x * canvasElement.width, y: lm[12].y * canvasElement.height };
      const el = { x: lm[14].x * canvasElement.width, y: lm[14].y * canvasElement.height };
      const wr = { x: lm[16].x * canvasElement.width, y: lm[16].y * canvasElement.height };
      const ang = angleBetween(sh, el, wr);
      updateRepCounter(ang);
      if (ang < 50) { formFeedback && (formFeedback.textContent = 'Good curl depth', formFeedback.style.color = 'green'); }
      else if (ang > 140) { formFeedback && (formFeedback.textContent = 'Extend arm', formFeedback.style.color = 'darkorange'); }
      else { formFeedback && (formFeedback.textContent = ''); }

    }
  }

  // --- MediaPipe Pose detection helpers (robust) ---
  function getPoseClass() {
    // Favor global Pose constructor from CDN
    if (typeof Pose !== 'undefined') {
      // new Pose(...) is the normal usage
      return Pose;
    }
    // try mpPose namespace
    if (typeof mpPose !== 'undefined' && mpPose.Pose) return mpPose.Pose;
    // try window.Pose.Pose style
    try {
      if (window.Pose && window.Pose.Pose) return window.Pose.Pose;
    } catch (e) { }
    return null;
  }

  function waitForMediaPipe(maxAttempts = 60, interval = 100) {
    return new Promise((resolve, reject) => {
      let attempts = 0;
      const id = setInterval(() => {
        attempts++;
        const PoseClass = getPoseClass();
        if (PoseClass) { clearInterval(id); resolve(PoseClass); return; }
        if (attempts >= maxAttempts) {
          clearInterval(id);
          const keys = Object.keys(window || {}).filter(k => /pose|mediapipe|MediaPipe/i.test(k)).slice(0, 20);
          console.error('MediaPipe not found, window keys (sample):', keys);
          reject(new Error('MediaPipe Pose failed to load after timeout.'));
        }
      }, interval);
    });
  }

  async function initPose() {
    try {
      const PoseClass = await waitForMediaPipe();
      // Use specific version to match index.html and avoid Module.arguments error
      pose = new PoseClass({ locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose@0.5.1675469404/${file}` });

      pose.setOptions({
        modelComplexity: 1,
        smoothLandmarks: true,
        enableSegmentation: false,
        minDetectionConfidence: 0.1, // Extreme Sensitivity
        minTrackingConfidence: 0.1
      });

      pose.onResults(onResults);
      console.log('MediaPipe Pose initialized with EXTREME settings (conf 0.1, complexity 1).');
    } catch (err) {
      console.error('initPose error', err);
      // alert('MediaPipe Pose init failed. Check console for details.');
    }
  }

  function ensureCanvasMatchesVideo() {
    if (!videoElement || !canvasElement) return;
    const vw = videoElement.videoWidth || 640;
    const vh = videoElement.videoHeight || 480;
    if (canvasElement.width !== vw || canvasElement.height !== vh) {
      canvasElement.width = vw; canvasElement.height = vh;
    }
  }

  // --- Camera start/stop ---
  async function startCamera() {
    if (camera) return;
    if (!pose) await initPose();
    if (!pose) { formFeedback && (formFeedback.textContent = 'Pose not initialized'); return; }

    try {
      if (typeof Camera !== 'undefined') {
        camera = new Camera(videoElement, {
          onFrame: async () => {
            if (document.body.classList.contains('modal-open')) return;
            try { ensureCanvasMatchesVideo(); await pose.send({ image: videoElement }); } catch (e) { console.error('pose.send error', e); }
          },
          width: 640, height: 480
        });
        await camera.start();
        console.log('Camera started (MediaPipe helper).');
      } else {
        // fallback to getUserMedia + animation loop
        const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
        videoElement.srcObject = stream; await videoElement.play();
        ensureCanvasMatchesVideo();
        let stopped = false;
        camera = { stop: () => { stopped = true; stream.getTracks().forEach(t => t.stop()); videoElement.pause(); videoElement.srcObject = null; } };
        (async function frameLoop() {
          if (stopped) return;
          if (document.body.classList.contains('modal-open')) { requestAnimationFrame(frameLoop); return; }
          try { await pose.send({ image: videoElement }); } catch (e) { console.error('pose.send fallback', e); }
          requestAnimationFrame(frameLoop);
        })();
        console.log('Camera started (getUserMedia fallback).');
      }
      startBtn && (startBtn.disabled = true);
      stopBtn && (stopBtn.disabled = false);
      snapshotBtn && (snapshotBtn.disabled = false);
      startBtn && (startBtn.disabled = true);
      stopBtn && (stopBtn.disabled = false);
      snapshotBtn && (snapshotBtn.disabled = false);
      formFeedback && (formFeedback.textContent = '');
      document.getElementById('cameraOverlay')?.classList.add('d-none');
    } catch (err) {
      console.error('startCamera failed', err);
      formFeedback && (formFeedback.textContent = 'Could not start camera: ' + (err.message || err));
      try { camera && camera.stop && camera.stop(); } catch (_) { }
      camera = null;
      startBtn && (startBtn.disabled = false);
      stopBtn && (stopBtn.disabled = true);
      startBtn && (startBtn.disabled = false);
      stopBtn && (stopBtn.disabled = true);
      snapshotBtn && (snapshotBtn.disabled = true);
      document.getElementById('cameraOverlay')?.classList.remove('d-none');
    }
  }

  async function stopCamera() {
    try {
      if (!camera) return;

      // Log workout if reps > 0
      if (repState.count > 0) {
        const token = getJWTToken();
        if (token) {
          // Non-blocking log
          fetchWithToken('/api/log_workout', {
            method: 'POST',
            body: JSON.stringify({
              reps: repState.count,
              workout_type: 'squat' // Default or dynamic
            })
          }).then(r => r.json()).then(data => {
            console.log('Workout logged:', data);
            if (data.streak_count !== undefined) updateGamificationUI(data);
          }).catch(e => console.error('Log workout failed', e));
        }
      }

      camera.stop && camera.stop();
      camera = null;
      canvasCtx && canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);
      startBtn && (startBtn.disabled = false);
      stopBtn && (stopBtn.disabled = true);
      startBtn && (startBtn.disabled = false);
      stopBtn && (stopBtn.disabled = true);
      snapshotBtn && (snapshotBtn.disabled = true);
      document.getElementById('cameraOverlay')?.classList.remove('d-none');
      console.log('Camera stopped');
    } catch (e) { console.error('stopCamera error', e); }
  }

  // wire camera controls (existing IDs)
  startBtn && startBtn.addEventListener('click', () => startCamera());
  stopBtn && stopBtn.addEventListener('click', () => stopCamera());


  // snapshot -> upload
  snapshotBtn && snapshotBtn.addEventListener('click', async () => { await doSnapshotUpload(); });

  async function doSnapshotUpload() {
    if (!canvasElement) { alert('No canvas available'); return; }
    const dataUrl = canvasElement.toDataURL('image/png');
    const blob = await (await fetch(dataUrl)).blob();
    const f = new File([blob], 'snapshot.png', { type: 'image/png' });
    const form = new FormData(); form.append('file', f); form.append('use_height', 'false');
    try {
      snapshotBtn.disabled = true; snapshotBtn.textContent = 'Sending...';
      const resp = await fetchWithToken('/api/upload', { method: 'POST', body: form });
      const text = await resp.text();
      if (!resp.ok) throw new Error(text || `${resp.status} ${resp.statusText}`);
      const j = JSON.parse(text);
      alert('Snapshot saved. Waist px: ' + (j.waist_px != null ? j.waist_px : 'N/A'));
      // refresh history with username/token if available
      const uname = (usernameInput?.value || '').trim();
      const token = getJWTToken();
      if (uname && token) await loadHistory({ username: uname, token });
    } catch (err) {
      console.error('snapshot upload error', err);
      alert('Snapshot upload failed: ' + (err.message || err));
    } finally {
      snapshotBtn.disabled = false; snapshotBtn.textContent = 'Snapshot → Server';
    }
  }

  // --- History handling (robust) ---
  let lastHistoryCreds = null;

  if (loadHistoryBtn) {
    loadHistoryBtn.addEventListener('click', async () => {
      const usernameVal = (usernameInput?.value || '').trim();
      if (!usernameVal) { alert('Please enter your Username first.'); return; }
      const tokenVal = getJWTToken();
      if (!tokenVal) { alert('Please generate or paste your Token first.'); return; }
      const ok = await loadHistory({ username: usernameVal, token: tokenVal });
      if (ok && historyCard) { historyCard.style.display = 'block'; historyCard.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    });
  }

  async function loadHistory(creds) {
    const target = creds || lastHistoryCreds;
    if (!target) return false;
    lastHistoryCreds = target;

    try {
      historyStatus && (historyStatus.textContent = 'Loading...');
      // Use fetchWithToken so X-API-KEY/Authorization header included
      const resp = await fetchWithToken('/api/get_history', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(target)
      });

      const text = await resp.text();
      if (!resp.ok) {
        // try parse json error
        let msg = text;
        try { const j = JSON.parse(text); msg = j.detail || j.error || JSON.stringify(j); } catch (_) { }
        historyStatus && (historyStatus.textContent = msg);
        if (resp.status === 401) alert('Access Denied: Invalid Token');
        else alert('Failed to load history: ' + msg);
        return false;
      }

      // success — backend may return { ok: true, items: [...] } or an array directly
      let data;
      try { data = JSON.parse(text); } catch (e) { data = text; }
      let items = [];
      if (Array.isArray(data)) items = data;
      else if (data && data.ok && Array.isArray(data.items)) items = data.items;
      else if (data && Array.isArray(data.items)) items = data.items;
      else if (data && data.items) items = data.items || [];
      else items = [];

      renderHistoryTable(items);
      historyStatus && (historyStatus.textContent = items.length ? '' : 'No history yet.');
      historyCard && (historyCard.style.display = items.length ? 'block' : 'block');
      return true;
    } catch (e) {
      console.error('loadHistory error', e);
      historyStatus && (historyStatus.textContent = 'Failed to load history: ' + e.message);
      alert('Failed to load history: ' + e.message);
      return false;
    }
  }

  function renderHistoryTable(items = []) {
    if (!historyBody) return;
    historyBody.innerHTML = '';
    items.forEach(item => {
      const tr = document.createElement('tr');

      // preview
      const previewTd = document.createElement('td');
      if (item.filename) {
        const img = document.createElement('img');
        img.src = `/uploads/${item.filename}`;
        img.style.width = '120px';
        img.style.borderRadius = '6px';
        // Handle 404: Replace with placeholder
        img.onerror = () => {
          img.src = 'https://placehold.co/120x120?text=No+Image';
          img.alt = 'Image not found';
        };
        previewTd.appendChild(img);
      } else {
        previewTd.textContent = '—';
      }

      const fnameTd = document.createElement('td'); fnameTd.textContent = item.filename || '—';
      const tsTd = document.createElement('td'); tsTd.textContent = item.timestamp || '—';
      const pxTd = document.createElement('td'); pxTd.textContent = item.waist_px != null ? String(item.waist_px) : '';
      const cmTd = document.createElement('td'); cmTd.textContent = (item.waist_cm != null && item.waist_cm !== undefined) ? (Number(item.waist_cm).toFixed(1)) : '';

      const workoutTd = document.createElement('td');
      const workoutBtn = document.createElement('button');
      workoutBtn.textContent = 'View Workout';
      workoutBtn.className = 'btn btn-sm btn-outline-primary';
      workoutBtn.addEventListener('click', () => showWorkoutModal(item.recommended_workouts || item.workouts || []));
      workoutTd.appendChild(workoutBtn);

      const actionTd = document.createElement('td');
      const delBtn = document.createElement('button');
      delBtn.textContent = 'Delete';
      delBtn.className = 'btn btn-sm btn-outline-danger';
      delBtn.addEventListener('click', async () => {
        if (!confirm('Delete this record?')) return;
        try {
          const dresp = await fetchWithToken(`/api/history/${item.id}`, { method: 'DELETE' });
          if (!dresp.ok) {
            const txt = await dresp.text();
            alert('Delete failed: ' + (txt || dresp.status));
          } else {
            await loadHistory(lastHistoryCreds);
          }
        } catch (err) {
          console.error('delete history error', err);
          alert('Delete error: ' + (err.message || err));
        }
      });
      actionTd.appendChild(delBtn);

      tr.appendChild(previewTd);
      tr.appendChild(fnameTd);
      tr.appendChild(tsTd);
      tr.appendChild(pxTd);
      tr.appendChild(cmTd);
      tr.appendChild(workoutTd);
      tr.appendChild(actionTd);

      historyBody.appendChild(tr);
    });
  }

  let workoutModalInstance = null;
  function showWorkoutModal(workouts = []) {
    if (!workoutModal || !modalWorkoutList) return;
    modalWorkoutList.innerHTML = workouts.length ? workouts.map(w => {
      const name = w.name || w.title || 'Exercise';
      const target = w.target_muscle || w.target || 'Full Body';
      const meta = [w.category, w.difficulty, w.environment].filter(Boolean).join(' • ');
      return `<li style="margin-bottom:8px;"><strong>${name}</strong><br/><small style="color:#8deaff;">${target}</small><br/><small>${meta}</small></li>`;
    }).join('') : '<li>No workout data stored for this entry.</li>';

    if (!workoutModalInstance) workoutModalInstance = safeGetModal(workoutModal);
    if (!workoutModal.classList.contains('show')) {
      workoutModalInstance.show();
    }
  }

  // Cleanup when modal is hidden (Bootstrap event)
  if (workoutModal) {
    workoutModal.addEventListener('hidden.bs.modal', () => {
      // any cleanup if needed
    });
  }

  // --- Tutorials ---
  function buildTutorialUrl(exName = '') {
    const q = encodeURIComponent(`how to do ${exName}`.trim());
    return `https://www.youtube.com/results?search_query=${q}`;
  }
  function buildTutorialEmbed(exName = '') {
    const q = encodeURIComponent(`how to do ${exName}`.trim());
    return `https://www.youtube.com/embed?listType=search&list=${q}`;
  }
  let tutorialModalInstance = null;
  function openTutorial(exName = 'Workout') {
    if (!tutorialModal || !tutorialTitle || !tutorialFrame || !tutorialLink) return;
    tutorialTitle.textContent = exName;
    tutorialFrame.src = buildTutorialEmbed(exName);
    tutorialLink.href = buildTutorialUrl(exName);

    if (!tutorialModalInstance) tutorialModalInstance = safeGetModal(tutorialModal);
    if (!tutorialModal.classList.contains('show')) {
      tutorialModalInstance.show();
    }
  }
  // Clear iframe when tutorial modal is hidden
  if (tutorialModal) {
    tutorialModal.addEventListener('hidden.bs.modal', () => {
      if (tutorialFrame) tutorialFrame.src = '';
    });
  }
  window.openTutorial = openTutorial;

  function handleManualSearch() {
    const term = (tutorialSearchInput?.value || '').trim();
    if (!term) { alert('Please type an exercise name.'); tutorialSearchInput?.focus(); return; }
    openTutorial(term);
  }
  window.handleManualSearch = handleManualSearch;

  // --- Render workouts (upload result) ---
  function renderWorkoutCards(workouts = []) {
    const workoutSection = document.getElementById('workoutSection');
    const workoutGrid = document.getElementById('workoutGrid');
    if (!workoutSection || !workoutGrid) return;
    if (!workouts || !workouts.length) { workoutSection.style.display = 'none'; return; }
    workoutGrid.innerHTML = workouts.map(w => {
      const name = w.name || w.title || 'Exercise';
      const target = w.target_muscle || w.target || 'Full Body';
      const meta = [w.category, w.difficulty, w.environment].filter(Boolean).join(' • ');
      const seniorBadge = w.is_senior_friendly ? '<span class="badge bg-success ms-2" style="font-size:0.7em">Senior Friendly</span>' : '';
      return `<div class="col-12 mb-2"><div class="card p-2"><div class="d-flex justify-content-between"><div><strong>${name}</strong>${seniorBadge}<div class="small">${target}</div><div class="small text-muted">${meta}</div></div><div><button class="btn btn-sm btn-outline-primary" onclick="openTutorial('${name.replace(/'/g, "\\'")}')">Learn</button></div></div></div></div>`;
    }).join('');
    workoutSection.style.display = 'block';
  }
  window.renderWorkoutCards = renderWorkoutCards;

  function hideWorkoutSection() {
    const workoutSection = document.getElementById('workoutSection');
    if (workoutSection) workoutSection.style.display = 'none';
  }
  window.hideWorkoutSection = hideWorkoutSection;





  // --- Gamification UI Helper ---
  function updateGamificationUI(data) {
    // 1. Update Streak
    const streakBadge = document.getElementById('streakBadge');
    const streakCount = document.getElementById('streakCount');
    if (streakBadge && streakCount && data.streak_count !== undefined) {
      streakCount.textContent = data.streak_count;
      streakBadge.style.display = 'flex';
      streakBadge.style.setProperty('display', 'flex', 'important');

      // Animate if increased (simple check logic would be needed for "increased", 
      // but for now just pulse on update)
      streakBadge.classList.add('pulse-animation'); // Add CSS for this if desired
    }

    // 2. Update Badges
    const earned = data.badges_earned || [];
    const newBadges = data.new_badges || [];

    // Show trophy case if any badges
    const trophySection = document.getElementById('trophyCaseSection');
    if (trophySection && earned.length > 0) {
      trophySection.style.display = 'block';

      earned.forEach(badge => {
        const el = document.getElementById(`badge-${badge}`);
        if (el) {
          el.classList.remove('opacity-25');
          el.classList.add('opacity-100');
          if (newBadges.includes(badge)) {
            el.style.transform = "scale(1.2)";
            setTimeout(() => el.style.transform = "scale(1)", 1000);
          }
        }
      });
    }
  }

  // --- Small helpers: wire top/bottom buttons if present ---
  const startBtnTop = document.getElementById('startBtnTop');
  if (startBtnTop && startBtn) startBtnTop.addEventListener('click', () => startBtn.click());
  const loadHistoryBtnTop = document.getElementById('loadHistoryBtnTop');
  const loadHistoryBtnBottom = document.getElementById('loadHistoryBtn');
  if (loadHistoryBtnTop && loadHistoryBtnBottom) loadHistoryBtnTop.addEventListener('click', () => loadHistoryBtnBottom.click());

  // --- Weekly Report ---
  const weeklyReportBtn = document.getElementById('weeklyReportBtn');
  const weeklyReportModal = document.getElementById('weeklyReportModal');
  let weeklyReportModalInstance = null;
  let weeklyReportLoading = false;
  let modalShown = false;

  // Initialize modal instance variable
  // We do NOT initialize it here blindly. We do it just-in-time or check existence.

  if (weeklyReportBtn) {
    weeklyReportBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopPropagation();

      // Prevent multiple simultaneous requests
      if (weeklyReportLoading) {
        console.log('Weekly report already loading, skipping...');
        return;
      }

      const usernameVal = (usernameInput?.value || '').trim();
      if (!usernameVal) {
        alert('Please enter your Username first.');
        return;
      }

      const tokenVal = getJWTToken();
      if (!tokenVal) {
        alert('Please generate or paste your Token first.');
        return;
      }

      weeklyReportLoading = true;
      console.log('Loading weekly report for:', usernameVal);

      try {
        await loadWeeklyReport({ username: usernameVal, token: tokenVal });
      } finally {
        weeklyReportLoading = false;
      }
    });
  }

  async function loadWeeklyReport(creds) {
    try {
      const resp = await fetchWithToken('/api/weekly_report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(creds)
      });

      if (!resp.ok) {
        const text = await resp.text();
        alert('Failed to load report: ' + text);
        return;
      }

      const data = await resp.json();
      console.log('Weekly report data received:', data);

      // Store data globally for deferred rendering
      window.globalReportData = data;

      // Update UI (stats)
      const totalScansEl = document.getElementById('wrTotalScans');
      const latestWaistEl = document.getElementById('wrLatestWaist');
      const changeEl = document.getElementById('wrWeeklyChange');
      const changeCard = document.getElementById('wrChangeCard');

      if (totalScansEl) totalScansEl.textContent = data.total_scans || 0;
      if (latestWaistEl) latestWaistEl.textContent = data.latest_waist || 0;

      const changeVal = data.weekly_change || 0;

      if (changeEl) changeEl.textContent = (changeVal > 0 ? '+' : '') + changeVal;

      // Speak Weekly Summary
      if (window.speakText) {
        const summary = `Here is your weekly report. You completed ${data.total_scans || 0} scans. Your latest waist measurement is ${data.latest_waist || 0} centimeters. Keep up the good work.`;
        window.speakText(summary, true);
      }

      // Color coding elements
      if (changeCard && changeEl) {
        changeCard.className = 'card p-3 text-center h-100'; // reset
        const titleEl = changeCard.querySelector('h6');

        if (changeVal < 0) {
          changeCard.classList.add('border-success', 'bg-success-subtle');
          if (titleEl) titleEl.className = 'text-success';
          changeEl.className = 'display-4 fw-bold text-success';
        } else if (changeVal > 0) {
          changeCard.classList.add('border-danger', 'bg-danger-subtle');
          if (titleEl) titleEl.className = 'text-danger';
          changeEl.className = 'display-4 fw-bold text-danger';
        } else {
          if (titleEl) titleEl.className = 'text-muted';
          changeEl.className = 'display-4 fw-bold';
        }
      }

      // Robust Modal Handling
      if (weeklyReportModal) {
        weeklyReportModalInstance = safeGetModal(weeklyReportModal, { focus: false });
        // Only call show if not already shown
        if (!weeklyReportModal.classList.contains('show')) {
          weeklyReportModalInstance.show();
        } else {
          // If already shown, manually trigger chart render because 'shown.bs.modal' won't fire
          renderWeeklyCharts(window.globalReportData);
        }
      }

    } catch (e) {
      console.error('Weekly report error:', e);
      alert('Error loading report: ' + e.message);
    }
  }

  // --- Chart Logic (Redesigned) ---
  // --- Chart Logic (Separated) ---
  let workoutChartInstance = null;
  let waistChartInstance = null;

  function renderWeeklyCharts(data) {
    if (!data || !window.Chart) return;

    // --- 1. Workout Chart (Bar) ---
    // --- 1. Workout Chart (Bar) ---
    const ctxWorkout = document.getElementById('workoutChart');
    if (ctxWorkout) {
      // Robust Destroy: Check by ID string and global var
      const existingWorkout = Chart.getChart("workoutChart");
      if (existingWorkout) existingWorkout.destroy();
      if (workoutChartInstance) {
        try { workoutChartInstance.destroy(); } catch (e) { }
        workoutChartInstance = null;
      }

      workoutChartInstance = new Chart(ctxWorkout, {
        type: 'bar',
        data: {
          labels: data.dates || [],
          datasets: [{
            label: 'Minutes',
            data: data.daily_activity || [],
            backgroundColor: '#00ff99', // Bright Green
            borderRadius: 6,
            barThickness: 20
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            title: { display: true, text: 'Workout Duration (Minutes)', color: '#00ff99', font: { size: 16 } },
            tooltip: {
              displayColors: false,
              backgroundColor: 'rgba(0,0,0,0.8)',
              titleColor: '#fff',
              bodyColor: '#fff',
              callbacks: {
                label: function (context) {
                  return context.parsed.y + ' mins';
                }
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              grid: { color: 'rgba(255,255,255,0.05)' },
              ticks: { stepSize: 5, color: '#e0e0e0' }
            },
            x: {
              grid: { display: false },
              ticks: { color: '#e0e0e0' }
            }
          }
        }
      });
    }

    // --- 2. Waist Chart (Line) ---
    // --- 2. Waist Chart (Line) ---
    const ctxWaist = document.getElementById('waistChart');
    if (ctxWaist) {
      // Robust Destroy: Check by ID string and global var
      const existingWaist = Chart.getChart("waistChart");
      if (existingWaist) existingWaist.destroy();
      if (waistChartInstance) {
        try { waistChartInstance.destroy(); } catch (e) { }
        waistChartInstance = null;
      }

      waistChartInstance = new Chart(ctxWaist, {
        type: 'line',
        data: {
          labels: Array.from({ length: data.waist_history.length }, (_, i) => `Scan ${i + 1}`),
          datasets: [{
            label: 'Waist (cm)',
            data: data.waist_history || [],
            borderColor: '#00c6ff', // Cyan
            backgroundColor: 'rgba(0, 198, 255, 0.1)',
            borderWidth: 4,
            tension: 0.4,
            pointBackgroundColor: '#ffffff',
            pointBorderWidth: 2,
            pointRadius: 5,
            fill: true
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            title: { display: true, text: 'Waist Trend (cm)', color: '#00c6ff', font: { size: 16 } }
          },
          scales: {
            y: {
              grid: { color: 'rgba(255,255,255,0.05)' },
              ticks: { color: '#e0e0e0' }
            },
            x: {
              grid: { display: false },
              display: false
            }
          }
        }
      });
    }
  }

  // Event Listener for Chart Rendering (Fixes "Invisible Chart" bug)
  if (weeklyReportModal) {
    weeklyReportModal.addEventListener('shown.bs.modal', () => {
      if (window.globalReportData) {
        renderWeeklyCharts(window.globalReportData);
      }
    });
  }

  // --- End DOMContentLoaded listener ---

  // Gamification Functions
  function updateGamificationUI(data) {
    if (!data) return;

    const gamificationSection = document.getElementById('gamificationSection');
    if (gamificationSection) gamificationSection.style.display = 'block';

    // Update streaks
    if (typeof data.login_streak !== 'undefined') {
      const el = document.getElementById('loginStreakVal');
      if (el) animateValue(el, 0, data.login_streak, 2000);
    }
    if (typeof data.workout_streak !== 'undefined') {
      const el = document.getElementById('workoutStreakVal');
      if (el) animateValue(el, 0, data.workout_streak, 2000);

      // Navbar Streak Badge
      const streakBadge = document.getElementById('streakBadge');
      const streakCount = document.getElementById('streakCount');
      if (streakBadge && streakCount) {
        streakBadge.style.setProperty('display', 'flex', 'important');
        animateValue(streakCount, 0, data.workout_streak, 2000);
      }
    } else if (typeof data.streak_count !== 'undefined') {
      // Fallback legacy
      const el = document.getElementById('workoutStreakVal');
      if (el) animateValue(el, 0, data.streak_count, 2000);
      const streakBadge = document.getElementById('streakBadge');
      const streakCount = document.getElementById('streakCount');
      if (streakBadge && streakCount) {
        streakBadge.style.setProperty('display', 'flex', 'important');
        animateValue(streakCount, 0, data.streak_count, 2000);
      }
    }

    if (typeof data.weekly_consistency !== 'undefined') {
      const el = document.getElementById('consistencyVal');
      if (el) el.textContent = data.weekly_consistency + "/7";
    } else if (typeof data.consistency_score !== 'undefined') {
      const el = document.getElementById('consistencyVal');
      if (el) el.textContent = data.consistency_score + "/7";
    }

    // Update Badges
    if (data.badges_earned) {
      data.badges_earned.forEach(badge => {
        const el = document.getElementById('badge-' + badge);
        if (el) {
          el.classList.remove('opacity-25');
          el.classList.add('opacity-100');
          el.style.textShadow = "0 0 10px rgba(255, 215, 0, 0.8)";
        }
      });
    }

    // New Badges Alert
    if (data.new_badges && data.new_badges.length > 0) {
      // Debounce alert or just show log
      console.log("New badges:", data.new_badges);
    }
  }

  window.fetchGamificationStats = async function () {
    try {
      const resp = await fetchWithToken('/api/gamification');
      if (resp.ok) {
        const data = await resp.json();
        updateGamificationUI(data);
      }
    } catch (e) {
      console.error("Gamification fetch error", e);
    }
  };

  // Allow global access explicitly
  window.updateGamificationUI = updateGamificationUI;

  // Initial call if token exists
  if (getJWTToken()) {
    window.fetchGamificationStats();
  }

  // Global Reset Function for Voice & Button

  window.resetRepCounter = function () {
    repState.count = 0;
    repState.state = "UP";
    repState.angleBuf = [];
    if (repCountEl) repCountEl.textContent = "0";
    if (repCountSideEl) repCountSideEl.textContent = "0";
    if (formFeedback) {
      formFeedback.textContent = "Counters Reset";
      formFeedback.className = "badge-stage";
    }

    // Call Backend API
    fetchWithToken('/api/reset_counter', { method: 'POST' })
      .then(r => console.log('Backend counter reset:', r))
      .catch(e => console.error('Backend reset failed', e));
  };

  if (resetBtn) {
    // Remove old listeners by cloning or just overriding if possible (ignoring previous simple adds)
    // For simplicity, we just add this one. It might double fire if not careful, 
    // but the previous one was likely an anonymous arrow function.
    // Ideally we replace the previous line.

    // Let's rely on this new one being the primary one or just overwrite the onclick if needed for cleanliness
    resetBtn.onclick = function () { window.resetRepCounter(); };
  }

}); // end DOMContentLoaded


