import cv2
import numpy as np
import mediapipe as mp

class AdvancedSquatAnalyzer:
    def __init__(self):
        self.feedback = "Form Analysis Active"
        self.color = (0, 255, 0) # Green
        self.error_joint = None # To store which joint to highlight (e.g., 'knees')

    def calculate_angle(self, a, b, c):
        """Calculates the angle between three points (a, b, c)."""
        a = np.array(a) # First
        b = np.array(b) # Mid
        c = np.array(c) # End
        
        radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
        angle = np.abs(radians * 180.0 / np.pi)
        
        if angle > 180.0:
            angle = 360 - angle
            
        return angle

    def analyze_frame(self, landmarks, image):
        """
        Analyzes the frame for specific squat errors.
        Returns: Processed image with overlays and current feedback text.
        """
        h, w, _ = image.shape
        self.feedback = "PERFECT FORM ✅"
        self.color = (0, 255, 0) # Green
        self.error_joint = None

        # --- EXTRACT COORDINATES ---
        # Helper to get (x, y) coordinates
        def get_coords(landmark_idx):
            return [landmarks[landmark_idx].x * w, landmarks[landmark_idx].y * h]

        # Legs
        left_hip = get_coords(23)
        right_hip = get_coords(24)
        left_knee = get_coords(25)
        right_knee = get_coords(26)
        left_ankle = get_coords(27)
        right_ankle = get_coords(28)
        left_heel = get_coords(29)
        
        # Torso (for back rounding)
        left_shoulder = get_coords(11)

        # --- 1. DEPTH CHECK (Basic) ---
        # Calculate angle at the knee (Hip-Knee-Ankle)
        knee_angle = self.calculate_angle(left_hip, left_knee, left_ankle)
        
        # We only check depth if they are actually squatting (hips are low)
        hip_y = left_hip[1]
        knee_y = left_knee[1]
        
        # If hips are descending (near knee height)
        if hip_y > (knee_y - 50): 
            if knee_angle > 100:
                self.feedback = "GO LOWER! 📉"
                self.color = (0, 0, 255) # Red
                self.error_joint = "hips"

        # --- 2. KNEE VALGUS CHECK (Advanced) ---
        # Calculate horizontal distance between knees vs ankles
        knee_width = abs(left_knee[0] - right_knee[0])
        ankle_width = abs(left_ankle[0] - right_ankle[0])

        # Avoid division by zero
        if ankle_width > 0:
            ratio = knee_width / ankle_width
            # If knees are significantly narrower than ankles (< 0.8)
            if ratio < 0.8: 
                self.feedback = "PUSH KNEES OUT! ↔️"
                self.color = (0, 0, 255) # Red
                self.error_joint = "knees"

        # --- 3. BACK ROUNDING CHECK (Advanced) ---
        # Calculate torso lean angle: Vertical line vs Shoulder-Hip line
        # Create a virtual point directly above the hip to represent "Vertical"
        vertical_point = [left_hip[0], left_hip[1] - 100] 
        torso_angle = self.calculate_angle(vertical_point, left_hip, left_shoulder)

        # If angle is large, they are leaning forward too much
        if torso_angle > 45:
            self.feedback = "KEEP CHEST UP! ⬆️"
            self.color = (0, 0, 255) # Red
            self.error_joint = "back"

        # --- 4. HEEL LIFT CHECK (Ultra-Advanced) ---
        # Check if heel is significantly higher than toes/ankle y-level
        # (This requires careful calibration, but basically heel y should be close to ankle y)
        # Simple heuristic: If heel y is much less (higher on screen) than ankle y
        if (left_ankle[1] - left_heel[1]) > 20: # Threshold of 20 pixels
             self.feedback = "KEEP HEELS DOWN! 🦶"
             self.color = (0, 0, 255)
             self.error_joint = "feet"

        # --- VISUAL FEEDBACK OVERLAYS ---
        
        # Draw Feedback Text
        cv2.rectangle(image, (0, 0), (w, 60), (0,0,0), -1) # Black banner
        cv2.putText(image, self.feedback, (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, self.color, 2, cv2.LINE_AA)

        # Draw Error Boxes
        if self.error_joint == "knees":
            # Draw box around knees
            cv2.rectangle(image, (int(left_knee[0]-30), int(left_knee[1]-30)), 
                                 (int(right_knee[0]+30), int(right_knee[1]+30)), (0, 0, 255), 3)
        
        elif self.error_joint == "back":
            # Draw line representing the back
            cv2.line(image, (int(left_shoulder[0]), int(left_shoulder[1])), 
                            (int(left_hip[0]), int(left_hip[1])), (0, 0, 255), 4)

        elif self.error_joint == "feet":
             cv2.circle(image, (int(left_heel[0]), int(left_heel[1])), 20, (0,0,255), -1)

        return image, self.feedback