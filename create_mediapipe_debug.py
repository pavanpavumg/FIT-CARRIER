# create_mediapipe_debug.py
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(BASE_DIR, "templates")
os.makedirs(templates_dir, exist_ok=True)
path = os.path.join(templates_dir, "mediapipe_debug.html")

html = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>MediaPipe Debug Page</title>
  <style>
    body { font-family: monospace; margin: 18px; }
    pre { background:#111; color:#bcd; padding:12px; border-radius:6px; max-height:60vh; overflow:auto;}
    .ok { color:green; font-weight:700; }
    .bad { color:crimson; font-weight:700; }
  </style>
</head>
<body>
  <h2>MediaPipe / Camera Diagnostic</h2>
  <p>This page runs a diagnostic script and prints results below. Open DevTools → Console as well for extra logs.</p>
  <div>
    <button id="runBtn">Run Diagnostic</button>
  </div>
  <h3>Results</h3>
  <pre id="out">Not run yet.</pre>

  <script>
  async function append(msg) {
    const o = document.getElementById('out');
    o.textContent += '\\n' + msg;
    console.log(msg);
  }

  async function runDiagnostic() {
    const out = document.getElementById('out');
    out.textContent = "=== MediaPipe debug start ===";
    try {
      append("window.mpPose: " + (typeof window.mpPose !== "undefined" ? "defined" : "undefined"));
      try {
        append("mpPose.Pose typeof: " + (window.mpPose && window.mpPose.Pose ? typeof window.mpPose.Pose : "mpPose.Pose not present"));
      } catch(e){ append("mpPose.Pose check error: " + e); }

      append("window.Camera: " + (typeof window.Camera !== "undefined" ? "defined" : "undefined"));
      try {
        const camCheck = (typeof window.Camera === "function") ? "Camera is function" : ((window.Camera && typeof window.Camera.Camera === "function") ? "Camera.Camera" : "Camera helper not a function");
        append("window.Camera (constructor check): " + camCheck);
      } catch(e){ append("Camera check error: " + e); }

      append("window.mpDrawing: " + (typeof window.mpDrawing !== "undefined" ? "defined" : "undefined"));
      append("window.Controls: " + (typeof window.Controls !== "undefined" ? "defined" : "undefined"));

      // constructor test
      try {
        if (window.mpPose && typeof window.mpPose.Pose === "function") {
          append("Can construct mpPose.Pose? yes (constructor present)");
        } else if (window.mpPose && window.mpPose.Pose) {
          append("mpPose.Pose exists but is not function: " + typeof window.mpPose.Pose);
        } else {
          append("mpPose.Pose constructor NOT present");
        }
      } catch(e){ append("construct test error: " + e); }

      // quick getUserMedia test
      try {
        append("Testing navigator.mediaDevices.getUserMedia...");
        const s = await navigator.mediaDevices.getUserMedia({video:true});
        append("getUserMedia OK — obtained stream with " + s.getTracks().length + " tracks");
        s.getTracks().forEach(t => t.stop());
      } catch(err) {
        append("getUserMedia failed: " + (err && err.name ? err.name + " — " + err.message : String(err)));
      }

    } catch(ex) {
      append("Diagnostic script error: " + ex);
    }
    append("=== MediaPipe debug end ===");
  }

  document.getElementById('runBtn').addEventListener('click', runDiagnostic);

  // Auto-run on load:
  window.addEventListener('load', () => {
    // delay a bit to allow CDN scripts to load if present
    setTimeout(runDiagnostic, 600);
  });
  </script>
</body>
</html>
"""

with open(path, "w", encoding="utf-8") as f:
    f.write(html)

print("Wrote debug page to:", path)
print("Open http://127.0.0.1:8000/mediapipe-debug after starting your FastAPI server.")
