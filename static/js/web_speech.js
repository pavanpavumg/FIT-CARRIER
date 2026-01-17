// static/js/web_speech.js

/**
 * Native Web Speech API Implementation for Fitness App
 * - Uses window.SpeechRecognition or window.webkitSpeechRecognition
 * - Handles voice commands for Camera, Counter, and Uploads
 * - Provides Text-to-Speech feedback
 */

// 1. Check Browser Support
// 1. Check Browser Support
var SpeechRecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition;
let isVoiceActive = false;

if (SpeechRecognitionClass) {
    recognition = new SpeechRecognitionClass();
    recognition.continuous = false; // We want single commands; auto-restart manually for stability
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    // --- Event Handlers ---

    recognition.onstart = function () {
        console.log("🎤 Voice Recognition Started");
        updateVoiceUI(true);
    };

    recognition.onend = function () {
        // If active, restart automatically (Always Listening Mode)
        if (isVoiceActive) {
            try {
                recognition.start();
            } catch (e) {
                // Ignore "already started" errors
            }
        } else {
            console.log("🎤 Voice Recognition Stopped");
            updateVoiceUI(false);
        }
    };

    recognition.onresult = function (event) {
        const transcript = event.results[0][0].transcript.toLowerCase().trim();
        console.log("🗣️ You said:", transcript);
        handleVoiceCommand(transcript);
    };

    recognition.onerror = function (event) {
        console.warn("⚠️ Voice Error:", event.error);
        if (event.error === 'not-allowed') {
            speak("Microphone access denied.");
            isVoiceActive = false;
            updateVoiceUI(false);
        }
    };
} else {
    console.warn("❌ Web Speech API not supported in this browser.");
    alert("Voice control is not supported in this browser. Try Chrome/Edge/Safari.");
}


// 2. Command Processing Logic
function handleVoiceCommand(command) {
    console.log("Processing command:", command);

    // --- 1. Start Camera ---
    const startPhrases = ["start camera", "let's go", "iron man mode", "start workout", "start"];
    if (startPhrases.some(phrase => command.includes(phrase))) {
        executeCommand("Start Camera", () => {
            const btn = document.getElementById('startBtn');
            if (btn) btn.click();
        }, "Starting Camera. Let's do this!");
        return;
    }

    // --- 2. Stop Camera ---
    const stopPhrases = ["stop camera", "pause workout", "finish him", "stop"];
    if (stopPhrases.some(phrase => command.includes(phrase))) {
        executeCommand("Stop Camera", () => {
            const btn = document.getElementById('stopBtn');
            if (btn) btn.click();
        }, "Stopping Camera. Great work!");
        return;
    }

    // --- 3. Reset Counter ---
    const resetPhrases = ["reset counter", "clear stats", "new set"];
    if (resetPhrases.some(phrase => command.includes(phrase))) {
        executeCommand("Reset Counter", () => {
            // Use global function if available (exposed in main_jwt.js)
            if (window.resetRepCounter) window.resetRepCounter();
            else {
                const btn = document.getElementById('resetBtn');
                if (btn) btn.click();
            }
        }, "Counter reset. Fresh start.");
        return;
    }

    // --- 4. Upload Photo ---
    const uploadPhrases = ["analyze me", "upload photo", "scan body", "scan"];
    if (uploadPhrases.some(phrase => command.includes(phrase))) {
        executeCommand("Upload Photo", () => {
            const fileInput = document.getElementById('file');
            if (fileInput) {
                fileInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                fileInput.click();
            }
        }, "Opening photo upload.");
        return;
    }

    // Unknown Command
    console.log("❓ Unknown command:", command);
}

// Helper to execute and speak
function executeCommand(actionName, actionFn, feedbackText) {
    console.log(`✅ Executing: ${actionName}`);
    speak(feedbackText);
    if (actionFn) actionFn();
}

// 3. Text-to-Speech Feedback
function speak(text) {
    if ('speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        window.speechSynthesis.speak(utterance);
    }
}

// 4. Global Toggle Function (Expected by HTML button)
window.toggleVoice = function () {
    if (!recognition) return;

    if (isVoiceActive) {
        isVoiceActive = false; // Flag stops auto-restart
        recognition.stop();
        speak("Voice paused");
    } else {
        isVoiceActive = true;
        try {
            recognition.start();
            speak("Voice active");
        } catch (e) {
            console.error("Start error:", e);
        }
    }
};

// 5. UI Helper
function updateVoiceUI(active) {
    const btn = document.getElementById('nativeVoiceBtn');
    const icon = document.getElementById('nativeVoiceIcon');
    const label = document.getElementById('nativeVoiceLabel');

    if (btn && icon && label) {
        if (active) {
            btn.classList.add('pulse-animation', 'btn-danger');
            btn.classList.remove('btn-secondary');
            icon.classList.remove('fa-microphone-slash');
            icon.classList.add('fa-microphone');
            label.textContent = "Listening...";
            // Change color to red/active
        } else {
            btn.classList.remove('pulse-animation', 'btn-danger');
            btn.classList.add('btn-secondary');
            icon.classList.add('fa-microphone-slash');
            icon.classList.remove('fa-microphone');
            label.textContent = "Voice Control";
        }
    }
}
