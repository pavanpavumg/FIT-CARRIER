import cv2
import numpy as np
import math

class SquatAnalyzer:
    def __init__(self):
        # State Machine
        # 0: Standing (Angle > 160)
        # 1: Descending (Angle decreasing)
        # 2: Bottom (Angle < 90)
        # 3: Ascending (Angle increasing)
        self.state = 0
        self.rep_count = 0
        self.valid_rep = False
        self.feedback = "Stand straight to start"
        
        # Smoothing (EMA)
        self.prev_knee_angle = None
        self.prev_hip_angle = None
        self.alpha = 0.2  # Smoothing factor (0.2 current + 0.8 previous)
        
        # Metrics
        self.min_depth = 180
        self.stability_score = 100.0
        self.movement_history = []
        
        # Thresholds
        self.STANDING_THRESH = 160
        self.DEPTH_THRESH = 90
        self.BACK_WARN_THRESH = 30  # Degrees of forward lean
        
    def calculate_angle(self, a, b, c):
        """Calculate angle between three points (a-b-c) in degrees."""
        a = np.array(a)  # First
        b = np.array(b)  # Mid
        c = np.array(c)  # End
        
        radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
        angle = np.abs(radians*180.0/np.pi)
        
        if angle > 180.0:
            angle = 360-angle
            
        return angle

    def calculate_vertical_angle(self, a, b):
        """Calculate angle of segment a-b relative to vertical."""
        # a = shoulder, b = hip
        # Vertical vector from hip is (0, -1)
        # Vector b->a is (a.x - b.x, a.y - b.y)
        
        delta_x = a[0] - b[0]
        delta_y = a[1] - b[1]
        
        # Angle with vertical (y-axis)
        # Atan2(dx, -dy) gives angle from vertical up
        angle_rad = math.atan2(abs(delta_x), abs(delta_y))
        angle_deg = math.degrees(angle_rad)
        
        return angle_deg

    def smooth_value(self, current, previous):
        """Apply Exponential Moving Average (EMA)."""
        if previous is None:
            return current
        return (current * self.alpha) + (previous * (1 - self.alpha))

    def analyze_frame(self, landmarks, image_shape):
        """
        Analyze a single frame of pose landmarks.
        
        Args:
            landmarks: List of MediaPipe Pose landmarks (normalized x, y, z)
            image_shape: (height, width) of the image
            
        Returns:
            dict: Analysis results and visual data
        """
        h, w = image_shape
        
        # Extract key landmarks (MediaPipe indices)
        # 11: Left Shoulder, 12: Right Shoulder
        # 23: Left Hip, 24: Right Hip
        # 25: Left Knee, 26: Right Knee
        # 27: Left Ankle, 28: Right Ankle
        
        # Use Left side for analysis (can be made dynamic)
        shoulder = [landmarks[11].x * w, landmarks[11].y * h]
        hip = [landmarks[23].x * w, landmarks[23].y * h]
        knee = [landmarks[25].x * w, landmarks[25].y * h]
        ankle = [landmarks[27].x * w, landmarks[27].y * h]
        
        # 1. Calculate Angles
        raw_knee_angle = self.calculate_angle(hip, knee, ankle)
        
        # 2. Apply Smoothing
        knee_angle = self.smooth_value(raw_knee_angle, self.prev_knee_angle)
        self.prev_knee_angle = knee_angle
        
        # Back Angle (Vertical Torso Angle)
        back_angle = self.calculate_vertical_angle(shoulder, hip)
        
        # 3. State Machine & Logic
        skeleton_color = (255, 255, 255) # White (Neutral)
        status_color = (0, 255, 0) # Green
        
        # Back Safety Check (Always active)
        back_safe = back_angle <= self.BACK_WARN_THRESH
        if not back_safe:
            self.feedback = "KEEP CHEST UP!"
            skeleton_color = (0, 0, 255) # Red
            status_color = (0, 0, 255)
            self.stability_score = max(0, self.stability_score - 0.5)
        
        # State Transitions
        # State Transitions
        if self.state == 0: # Standing
            if knee_angle < self.STANDING_THRESH - 10: # Started descent
                self.state = 1
                self.feedback = "Descending"
                self.valid_rep = False
                self.min_depth = 180
            else:
                self.feedback = "Stand straight to start"
                
        elif self.state == 1: # Descending
            self.min_depth = min(self.min_depth, knee_angle)
            if knee_angle < self.DEPTH_THRESH:
                self.state = 2
                self.valid_rep = True # Hit depth
                # Check for perfect form at bottom
                if back_safe:
                    self.feedback = "Perfect Form! ✅"
                    skeleton_color = (0, 255, 0) # Green
                else:
                    self.feedback = "Keep Chest Up! ⚠️"
                    skeleton_color = (0, 0, 255) # Red
            elif knee_angle > self.prev_knee_angle + 5: # Started ascending early
                self.state = 3
                self.feedback = "Go Lower! 📉"
                skeleton_color = (0, 255, 255) # Yellow
                
        elif self.state == 2: # Bottom
            self.min_depth = min(self.min_depth, knee_angle)
            
            # Continuous check at bottom
            if back_safe:
                 if knee_angle < self.DEPTH_THRESH:
                    self.feedback = "Perfect Form! ✅"
                    skeleton_color = (0, 255, 0) # Green
            else:
                self.feedback = "Keep Chest Up! ⚠️"
                skeleton_color = (0, 0, 255) # Red

            if knee_angle > self.DEPTH_THRESH + 10:
                self.state = 3
                self.feedback = "Rising"
                
        elif self.state == 3: # Ascending
            if knee_angle > self.STANDING_THRESH:
                self.state = 0
                if self.valid_rep and back_safe:
                    self.rep_count += 1
                    self.feedback = "Rep Completed!"
                    self.stability_score = min(100, self.stability_score + 1)
                elif not self.valid_rep:
                    self.feedback = "Rep Invalid: Too Shallow"
                    self.stability_score -= 5
                elif not back_safe:
                    self.feedback = "Rep Invalid: Bad Back"
        
        # Update Stability Score (simple jitter penalty)
        if len(self.movement_history) > 5:
            jitter = abs(knee_angle - self.movement_history[-1])
            if jitter > 5: # Sudden jump
                self.stability_score = max(0, self.stability_score - 1)
        self.movement_history.append(knee_angle)
        if len(self.movement_history) > 30: self.movement_history.pop(0)
        
        return {
            "knee_angle": int(knee_angle),
            "back_angle": int(back_angle),
            "state": self.state,
            "rep_count": self.rep_count,
            "feedback": self.feedback,
            "skeleton_color": skeleton_color,
            "valid_rep": self.valid_rep,
            "stability_score": int(self.stability_score),
            "landmarks": {
                "shoulder": shoulder,
                "hip": hip,
                "knee": knee,
                "ankle": ankle
            }
        }

    def draw_visuals(self, image, result):
        """Draw skeleton and feedback on image."""
        color = result["skeleton_color"]
        lms = result["landmarks"]
        
        # Draw segments
        # Back line color based on back angle safety
        back_color = (0, 255, 0) if result["back_angle"] <= self.BACK_WARN_THRESH else (0, 0, 255)
        
        cv2.line(image, tuple(map(int, lms["shoulder"])), tuple(map(int, lms["hip"])), back_color, 3)
        cv2.line(image, tuple(map(int, lms["hip"])), tuple(map(int, lms["knee"])), color, 3)
        cv2.line(image, tuple(map(int, lms["knee"])), tuple(map(int, lms["ankle"])), color, 3)
        
        # Draw joints
        for pt in lms.values():
            cv2.circle(image, tuple(map(int, pt)), 5, (0, 255, 255), -1)
            
        # Draw Feedback Text
        cv2.putText(image, f"Reps: {result['rep_count']}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(image, f"State: {result['state']}", (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
        
        # Display Back Angle
        hip_pt = tuple(map(int, lms["hip"]))
        cv2.putText(image, f"{result['back_angle']} deg", (hip_pt[0] + 10, hip_pt[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, back_color, 2)

        # Feedback Color
        fb_color = (0, 255, 0) if "Perfect" in result["feedback"] or "Completed" in result["feedback"] else (0, 0, 255)
        if "Lower" in result["feedback"]: fb_color = (0, 255, 255) # Yellow
        if result["feedback"] == "Stand straight to start": fb_color = (255, 255, 255)
        
        cv2.putText(image, result["feedback"], (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, fb_color, 2)
        
        # Stability Score
        cv2.putText(image, f"Form Score: {result['stability_score']}%", (image.shape[1] - 250, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 0), 2)
        
        return image
