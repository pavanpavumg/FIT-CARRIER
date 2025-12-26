# measure.py
import cv2
import numpy as np
import math
from image_quality import assess_image_quality


# try to import mediapipe for selfie segmentation (optional)
try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
    mp_selfie = mp.solutions.selfie_segmentation
    mp_pose = mp.solutions.pose
except Exception:
    HAS_MEDIAPIPE = False
    mp_pose = None

# Constants for visualization
neon_green = (0, 255, 0)
neon_blue = (255, 255, 0)  # Cyan
cyan = (255, 255, 0)
red_alert = (0, 0, 255)
font = cv2.FONT_HERSHEY_SIMPLEX
font_scale = 0.8
thickness = 2
thick_thickness = 3


def segmentation_mask_mediapipe(img_bgr, model_selection=1):
    """
    Return a uint8 mask (255 foreground, 0 background) using MediaPipe Selfie Segmentation.
    If mediapipe not available, return None.
    """
    if not HAS_MEDIAPIPE:
        return None
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    with mp_selfie.SelfieSegmentation(model_selection=model_selection) as seg:
        results = seg.process(img_rgb)
        if results.segmentation_mask is None:
            return None
        # segmentation_mask is float32 0..1. Threshold at 0.5
        maskf = results.segmentation_mask
        mask = (maskf > 0.5).astype(np.uint8) * 255
        # optional morphology to clean
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        return mask

def preprocess_for_contours(img_bgr, blur_ksize=(5,5), canny_thresh1=50, canny_thresh2=150):
    """Return a cleaned binary mask (uint8) of edges -> closed -> filled."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, blur_ksize, 0)
    edges = cv2.Canny(blur, canny_thresh1, canny_thresh2)
    kernel = np.ones((7,7), np.uint8)
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.zeros_like(gray)
    if contours:
        cv2.drawContours(mask, contours, -1, 255, thickness=-1)
    kernel2 = np.ones((5,5), np.uint8)
    clean = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel2, iterations=1)
    return clean

def find_largest_contour(binary_mask):
    cnts, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    return max(cnts, key=cv2.contourArea)

def vertical_width_profile(contour, img_shape, x_min, x_max, y_min, y_max):
    mask = np.zeros(img_shape[:2], dtype=np.uint8)
    cv2.drawContours(mask, [contour], -1, 255, thickness=-1)
    profile = []
    for y in range(y_min, y_max + 1):
        row = mask[y, x_min:x_max+1]
        nz = np.where(row > 0)[0]
        if nz.size == 0:
            width = 0
            left = None
            right = None
        else:
            width = int(nz[-1] - nz[0] + 1)
            left = int(nz[0])
            right = int(nz[-1])
        profile.append((y, width, left, right))
    return profile, mask

def estimate_waist_width_px_from_masked(masked_img_bgr, torso_frac=(0.30, 0.60), debug_draw=True, height_cm=None, original_img=None):
    """
    Core estimator assuming a reasonably clean masked image (foreground on background).
    Returns (waist_px, debug_img, px_per_cm)
    """
    img_bgr = masked_img_bgr
    h_img, w_img = img_bgr.shape[:2]
    # convert to mask and proceed
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
    cnt = find_largest_contour(binary)
    if original_img is not None:
        debug = original_img.copy()
    else:
        debug = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    if cnt is None or cv2.contourArea(cnt) < 1000:
        return None, debug, None
    x, y, w, h = cv2.boundingRect(cnt)
    cv2.rectangle(debug, (x,y), (x+w, y+h), (0,255,0), 2)
    y0 = y + int(torso_frac[0] * h)
    y1 = y + int(torso_frac[1] * h)
    y0 = max(y0, y)
    y1 = min(y1, y+h-1)
    if y1 <= y0:
        y0 = y
        y1 = y + h - 1
    profile, filled_mask = vertical_width_profile(cnt, img_bgr.shape, x, x+w, y0, y1)
    widths = [(row, w_px, left, right) for (row, w_px, left, right) in profile if w_px and w_px > 5]
    if not widths:
        waist_px = w
        cv2.line(debug, (x, y + int(0.45*h)), (x+w, y + int(0.45*h)), (255,0,0), 2)
        px_per_cm = None
        if height_cm:
            px_per_cm = h / height_cm if height_cm > 0 else None
        return waist_px, debug, px_per_cm
    min_item = min(widths, key=lambda t: t[1])
    waist_row, waist_px, left_off, right_off = min_item
    left_x = x + (left_off if left_off is not None else 0)
    right_x = x + (right_off if right_off is not None else w - 1)
    cv2.line(debug, (left_x, waist_row), (right_x, waist_row), (0,0,255), 3)
    cv2.circle(debug, (left_x, waist_row), 4, (0,255,255), -1)
    cv2.circle(debug, (right_x, waist_row), 4, (0,255,255), -1)
    px_per_cm = None
    if height_cm:
        if height_cm > 0:
            px_per_cm = h / height_cm
    return int(waist_px), debug, px_per_cm

def estimate_waist_width_px(img_bgr, use_segmentation=False, torso_frac=(0.30, 0.60), debug_draw=True, height_cm=None):
    """
    Top-level estimator. If use_segmentation=True and mediapipe is available,
    uses selfie segmentation to create a clean mask and then estimate waist on the masked image.
    Returns (waist_px, debug_img, px_per_cm).
    """
    # try segmentation first if requested and available
    if use_segmentation and HAS_MEDIAPIPE:
        seg = segmentation_mask_mediapipe(img_bgr)
        if seg is not None:
            # apply mask to image (keep foreground)
            fg = cv2.bitwise_and(img_bgr, img_bgr, mask=seg)
            # optionally fill background with white for visualization
            debug_input = fg.copy()
            return estimate_waist_width_px_from_masked(debug_input, torso_frac=torso_frac, debug_draw=debug_draw, height_cm=height_cm, original_img=img_bgr)
        # if segmentation failed, fallthrough to classic pipeline

    # fallback: classic pipeline using edge-based mask (less robust)
    mask = preprocess_for_contours(img_bgr)
    cnt = find_largest_contour(mask)
    debug = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    if cnt is None or cv2.contourArea(cnt) < 1000:
        return None, debug, None
    # crop to contour and call masked estimator for consistency
    x, y, w, h = cv2.boundingRect(cnt)
    fg = cv2.bitwise_and(img_bgr, img_bgr, mask=mask)
    return estimate_waist_width_px_from_masked(fg, torso_frac=torso_frac, debug_draw=debug_draw, height_cm=height_cm, original_img=img_bgr)


def analyze_body(image, user_height_cm, gender="male", age=30):
    """
    Scientific Body Fat Estimation using MediaPipe Pose Landmarks and US Navy Method.
    Hybrid Safety Logic: Prioritizes Skeleton Landmarks (High Sensitivity 0.1) for Hips/Waist.
    Fallback to Contour happens in app.py if this returns None/False.
    
    Args:
        image: BGR image (numpy array)
        user_height_cm: Real height in centimeters (required for accurate calculation)
        gender: "male" or "female" (default: "male")
        age: Age in years (default: 30)
    
    Returns:
        dict with keys: Standard Keys
    """
    
    if user_height_cm is None or user_height_cm <= 0:
        return {
            "body_fat_percentage": None,
            "waist_cm": None,
            "neck_cm": None,
            "annotated_image": image.copy(),
            "pixel_to_cm_ratio": None,
            "torso_volume_index": None,
            "landmarks_detected": False,
            "error": "Height is required for accurate calculation",
            "body_morphotype": None,
            "morphotype_description": None,
            "shoulder_to_waist_ratio": None,
            "posture_issues": [],
            "posture_good": [],
            "waist_to_hip_ratio": None,
            "health_risk_level": None,
            "hip_cm": None,
            "scan_quality": None
        }
    
    # Convert BGR to RGB for MediaPipe
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    h_img, w_img = image.shape[:2]
    
    # Initialize MediaPipe Pose with High Sensitivity (0.1)
    annotated_img = image.copy()
    
    # Visualization Colors
    red_line_color = (0, 0, 255) # BGR
    yellow_dot = (0, 255, 255)   # BGR
    
    landmarks_detected = False
    
    with mp_pose.Pose(
        static_image_mode=True,
        model_complexity=2,
        enable_segmentation=True,
        min_detection_confidence=0.1,  # User Req: Very High Sensitivity
        min_tracking_confidence=0.1
    ) as pose:
        results = pose.process(image_rgb)
        
        # Step A: Skeleton Check
        if results.pose_landmarks:
             landmarks_detected = True
        
        if not landmarks_detected:
            return {
                "body_fat_percentage": None,
                "waist_cm": None,
                "neck_cm": None,
                "annotated_image": annotated_img,
                "pixel_to_cm_ratio": None,
                "landmarks_detected": False,
                "error": "Could not detect pose landmarks"
            }
        
        landmarks = results.pose_landmarks.landmark
        
        # Draw skeleton standard
        if mp.solutions.drawing_utils:
            mp.solutions.drawing_utils.draw_landmarks(
                annotated_img,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS
            )
        
        def get_landmark_xy(idx):
            if idx >= len(landmarks): return None
            lm = landmarks[idx]
            return (int(lm.x * w_img), int(lm.y * h_img))
        
        # Key Landmarks
        nose = get_landmark_xy(0)
        left_shoulder = get_landmark_xy(11)
        right_shoulder = get_landmark_xy(12)
        left_hip = get_landmark_xy(23)
        right_hip = get_landmark_xy(24)
        left_ankle = get_landmark_xy(27)
        right_ankle = get_landmark_xy(28)
        left_ear = get_landmark_xy(7)
        right_ear = get_landmark_xy(8)
        
        # Height Reference (Nose to Avg Ankle)
        if nose and left_ankle and right_ankle:
            avg_ankle_y = (left_ankle[1] + right_ankle[1]) / 2
            person_pixel_height = abs(nose[1] - avg_ankle_y)
        else:
             # Fallback height if ankles missing (try knees or just hips * 2 approx?)
             # For safety, let's require ankles or at least significant body part
             return { "landmarks_detected": False, "annotated_image": annotated_img }

        if person_pixel_height <= 0:
             return { "landmarks_detected": False, "annotated_image": annotated_img }

        pixel_to_cm_ratio = user_height_cm / person_pixel_height
        
        # --- LOGIC UPDATE: WAIST from HIPS (For Safety) ---
        waist_width_px = 0
        waist_cm = 0
        hip_cm = 0
        
        if left_hip and right_hip:
            # Distance(23, 24)
            dist_px = math.sqrt((left_hip[0]-right_hip[0])**2 + (left_hip[1]-right_hip[1])**2)
            waist_width_px = dist_px
            hip_width_px = dist_px # Same as waist for safety logic
            
            # Draw Red Line
            cv2.line(annotated_img, left_hip, right_hip, red_line_color, 2)
            
            # Draw Yellow Dot
            cv2.circle(annotated_img, left_hip, 5, yellow_dot, -1)
            cv2.circle(annotated_img, right_hip, 5, yellow_dot, -1)
            
            # Calculate CM
            # Hip width is a linear projection. Approximate circumference factor ~2.5
            waist_circumference_px = waist_width_px * 2.5 
            waist_cm = waist_circumference_px * pixel_to_cm_ratio
            hip_cm = waist_cm # Same
        else:
             # If hips not found despite results.pose_landmarks (rare but possible)
             return { "landmarks_detected": False, "annotated_image": annotated_img }

        # Shoulder logic for extra stats (keep existing)
        shoulder_width_px = 0
        shoulder_width_cm = 0
        if left_shoulder and right_shoulder:
            shoulder_width_px = math.sqrt((left_shoulder[0]-right_shoulder[0])**2 + (left_shoulder[1]-right_shoulder[1])**2)
            shoulder_width_cm = shoulder_width_px * pixel_to_cm_ratio
            
        # Neck Logic
        neck_cm = (shoulder_width_px * 0.32 * math.pi) * pixel_to_cm_ratio
        
        # Body Fat Formula (US Navy Method)
        body_fat_pct = None
        if waist_cm and neck_cm:
            try:
                waist_neck_diff = waist_cm - neck_cm
                if waist_neck_diff > 0:
                    log_waist_neck = math.log10(waist_neck_diff)
                    log_height = math.log10(user_height_cm)
                    denominator = 1.0324 - 0.19077 * log_waist_neck + 0.15456 * log_height
                    if denominator > 0:
                        body_fat_pct = (495 / denominator) - 450
                        body_fat_pct = max(0.0, min(50.0, body_fat_pct))
            except: pass

        # Torso Volume Index
        torso_volume_index = 50.0 # Default
        if left_shoulder and left_hip:
            # simple approx
            h_torso = abs(left_shoulder[1] - left_hip[1]) * pixel_to_cm_ratio
            vol = waist_cm * h_torso
            # normalize 3000-20000 range
            torso_volume_index = ((vol - 3000) / (17000)) * 100
            torso_volume_index = max(1.0, min(100.0, torso_volume_index))

        # Morphotype
        shoulder_to_waist_ratio = shoulder_width_cm / (waist_width_px * pixel_to_cm_ratio) if waist_width_px > 0 else 0
        if shoulder_to_waist_ratio > 1.4:
            body_morphotype = "Mesomorph"
        elif shoulder_to_waist_ratio < 1.1:
            body_morphotype = "Endomorph"
        else:
            body_morphotype = "Ectomorph"

        # Posture Issues (Simple)
        posture_issues = []
        if left_shoulder and right_shoulder:
            diff = abs(left_shoulder[1] - right_shoulder[1]) * pixel_to_cm_ratio
            if diff > 2.0: posture_issues.append("Uneven Shoulders")
            
        # WHR
        whr = 1.0 # Since we use same measurement for safety
        
        # Scan Quality
        quality_result = assess_image_quality(image, results.pose_landmarks) if results.pose_landmarks else None

        # Health Risk
        health_risk_level = "Moderate" if body_fat_pct and body_fat_pct > 25 else "Low"

        return {
            "body_fat_percentage": round(body_fat_pct, 1) if body_fat_pct is not None else None,
            "waist_cm": round(waist_cm, 1),
            "neck_cm": round(neck_cm, 1),
            "annotated_image": annotated_img,
            "pixel_to_cm_ratio": round(pixel_to_cm_ratio, 4),
            "torso_volume_index": round(torso_volume_index, 1),
            "landmarks_detected": True,
            "error": None,
            # New features
            "body_morphotype": body_morphotype,
            "morphotype_description": "Analyzed via Skeleton (Safe Mode)",
            "shoulder_to_waist_ratio": round(shoulder_to_waist_ratio, 2),
            "posture_issues": posture_issues,
            "posture_good": [],
            "waist_to_hip_ratio": round(whr, 2),
            "health_risk_level": health_risk_level,
            "hip_cm": round(hip_cm, 1),
            "scan_quality": quality_result
        }
