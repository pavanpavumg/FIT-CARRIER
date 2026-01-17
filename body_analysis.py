import cv2
import numpy as np
import math
import mediapipe as mp
import measure

# Initialize MediaPipe
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

def analyze_physique(image, height_cm=None):
    """
    Advanced Body Analysis: Morphotype, Posture, Health Risk, and Visuals.
    
    Args:
        image: BGR image (numpy array)
        height_cm: User's height in cm (optional, for scaling)
        
    Returns:
        dict: Analysis results and annotated image
    """
    h, w = image.shape[:2]
    annotated_img = image.copy()
    
    # Run MediaPipe Pose
    with mp_pose.Pose(
        static_image_mode=True,
        model_complexity=2,
        enable_segmentation=True,
        min_detection_confidence=0.5
    ) as pose:
        results = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        
        if not results.pose_landmarks:
            return {"error": "No pose detected", "image": annotated_img}
            
        landmarks = results.pose_landmarks.landmark
        
        # Helper to get coords
        def get_xy(idx):
            return (int(landmarks[idx].x * w), int(landmarks[idx].y * h))
            
        # Key Landmarks
        l_shoulder = get_xy(11)
        r_shoulder = get_xy(12)
        l_hip = get_xy(23)
        r_hip = get_xy(24)
        l_ear = get_xy(7)
        r_ear = get_xy(8)
        l_ankle = get_xy(27)
        r_ankle = get_xy(28)
        
        # --- 1. Body Morphotype (Somatotype) ---
        shoulder_width = math.dist(l_shoulder, r_shoulder)
        hip_width = math.dist(l_hip, r_hip)
        
        if hip_width > 0:
            sw_ratio = shoulder_width / hip_width
        else:
            sw_ratio = 1.0
            
        if sw_ratio > 1.4:
            morphotype = "Mesomorph"
            morpho_desc = "Athletic/Muscular"
        elif sw_ratio < 1.1:
            morphotype = "Endomorph"
            morpho_desc = "Higher fat storage"
        else:
            morphotype = "Ectomorph"
            morpho_desc = "Lean/Average"
            
        # --- 2. Static Posture Analysis ---
        posture_issues = []
        posture_good = []
        
        # A. Shoulder Imbalance
        # Calculate subject height in pixels (approximate)
        # Use ankle to eye/ear vertical dist
        subject_height_px = abs((l_ankle[1] + r_ankle[1])/2 - (l_ear[1] + r_ear[1])/2)
        if subject_height_px == 0: subject_height_px = h # Fallback
        
        shoulder_y_diff = abs(l_shoulder[1] - r_shoulder[1])
        if shoulder_y_diff > 0.02 * subject_height_px:
            posture_issues.append("Uneven Shoulders")
            # Draw Red Alert Lines
            cv2.line(annotated_img, l_shoulder, r_shoulder, (0, 0, 255), 3)
        else:
            posture_good.append("Shoulders Balanced")
            # Draw Green Line
            cv2.line(annotated_img, l_shoulder, r_shoulder, (0, 255, 0), 2)
            
        # B. Forward Head Posture (Text Neck)
        ear_x_avg = (l_ear[0] + r_ear[0]) / 2
        shoulder_x_avg = (l_shoulder[0] + r_shoulder[0]) / 2
        
        if landmarks[11].visibility > 0.8 and landmarks[12].visibility < 0.5: # Left side view
            fhp_diff = l_ear[0] - l_shoulder[0]
            if abs(fhp_diff) > 0.1 * subject_height_px:
                 posture_issues.append("Forward Head Posture")
        elif landmarks[12].visibility > 0.8 and landmarks[11].visibility < 0.5: # Right side view
             fhp_diff = r_ear[0] - r_shoulder[0]
             if abs(fhp_diff) > 0.1 * subject_height_px:
                 posture_issues.append("Forward Head Posture")
        else:
            pass

        # --- 3. Health Risk Indicator (WHR) ---
        waist_px = None
        if results.segmentation_mask is not None:
             pass
        
        try:
            waist_px, _, _ = measure.estimate_waist_width_px(image, height_cm=height_cm)
        except AttributeError:
            waist_px = hip_width * 0.8 # Rough guess
            
        if waist_px and hip_width > 0:
            whr = waist_px / hip_width
            if whr > 0.9:
                risk_level = "High Risk"
            else:
                risk_level = "Low Risk"
        else:
            whr = 0
            risk_level = "Unknown"
            
        # --- 4. Visual Output (Cyberpunk Style) ---
        # Neon Blue Triangle (V-Taper)
        mid_hip = ((l_hip[0] + r_hip[0])//2, (l_hip[1] + r_hip[1])//2)
        triangle_cnt = np.array([l_shoulder, r_shoulder, mid_hip], np.int32)
        
        # Draw filled triangle with transparency
        overlay = annotated_img.copy()
        cv2.drawContours(overlay, [triangle_cnt], 0, (255, 255, 0), -1) # Cyan/Neon Blue
        cv2.addWeighted(overlay, 0.3, annotated_img, 0.7, 0, annotated_img)
        
        # Draw outline
        cv2.drawContours(annotated_img, [triangle_cnt], 0, (255, 255, 0), 2)
        
        # Draw Green Checkmarks if good posture
        if not posture_issues:
            cv2.putText(annotated_img, "POSTURE OK", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        else:
             cv2.putText(annotated_img, "POSTURE ALERT", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
             for i, issue in enumerate(posture_issues):
                 cv2.putText(annotated_img, issue, (50, 140 + i*30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        return {
            "morphotype": morphotype,
            "morphotype_desc": morpho_desc,
            "shoulder_to_waist_ratio": round(sw_ratio, 2),
            "posture_issues": posture_issues,
            "whr": round(whr, 2),
            "risk_level": risk_level,
            "annotated_image": annotated_img
        }

# --- NEW REALITY FILTER FUNCTIONS ---

def get_expected_waist(gender, height_cm):
    """
    Returns the average healthy waist size based on height and gender.
    Rule of Thumb: Waist should be roughly 45-50% of height.
    """
    if str(gender).lower() == 'male':
        return height_cm * 0.48  # Men: ~48% of height
    else:
        return height_cm * 0.45  # Women: ~45% of height

def smart_body_analysis(image, user_height_cm, user_gender, user_age):
    """
    Analyzes waist with Reality Filter:
    1. Standard CV measurement.
    2. Validates against expected averages based on height/gender/age.
    3. Smooths result if deviation > 25cm.
    
    Args:
        image: BGR numpy array (from cv2.imread or decode).
        user_height_cm: float
        user_gender: str ("male"/"female")
        user_age: int
        
    Returns:
        tuple: (annotated_image, final_waist_cm)
    """
    if image is None: return None, 0.0

    # 1. Standard Computer Vision Analysis (Edge-based)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours: return image, 0.0

    # 2. Get Raw Measurement from Camera
    person_contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(person_contour)
    
    if h == 0: return image, 0.0

    pixel_ratio = user_height_cm / h
    # Estimate waist is 80% of body width
    # Note: 'w' here is bounding box width.
    raw_waist_pixels = w * 0.8  
    camera_waist_cm = raw_waist_pixels * pixel_ratio

    # --- 3. THE REALITY CHECK ---
    expected_waist = get_expected_waist(user_gender, user_height_cm)
    
    # Calculate Deviation
    difference = abs(camera_waist_cm - expected_waist)
    
    final_result = camera_waist_cm

    # LOGIC: If camera is VERY wrong (> 25cm difference), blend with average.
    if difference > 25.0:
        print(f"DEBUG: Camera Error Detected ({camera_waist_cm:.1f}cm vs expected {expected_waist:.1f}cm). Smoothing result.")
        # Blend 20% Camera + 80% Average
        final_result = (camera_waist_cm * 0.2) + (expected_waist * 0.8)
    
    # LOGIC: Age Adjustment
    if user_age > 30:
        final_result += (user_age - 30) * 0.1 # Add small buffer for age

    # 4. Draw Visuals
    mid_y = y + int(h * 0.55) 
    # Ensure mid_y is within image
    mid_y = min(max(mid_y, 0), image.shape[0]-1)
    
    cv2.line(image, (x, mid_y), (x+w, mid_y), (0,0,255), 4)
    cv2.putText(image, f"{final_result:.1f}cm", (x, mid_y-10), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,0,255), 2)

    return image, round(final_result, 1)
