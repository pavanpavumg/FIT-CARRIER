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
    
    Args:
        image: BGR image (numpy array)
        user_height_cm: Real height in centimeters (required for accurate calculation)
        gender: "male" or "female" (default: "male")
        age: Age in years (default: 30)
    
    Returns:
        dict with keys:
            - body_fat_percentage: Calculated body fat % (or None if calculation failed)
            - waist_cm: Waist circumference in cm
            - neck_cm: Neck circumference in cm
            - annotated_image: BGR image with measurement lines drawn
            - pixel_to_cm_ratio: Conversion factor
            - torso_volume_index: Muscle mass indicator (1-100)
            - landmarks_detected: Boolean indicating if pose was detected
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
    
    # Initialize MediaPipe Pose
    annotated_img = image.copy()
    
    with mp_pose.Pose(
        static_image_mode=True,
        model_complexity=2,
        enable_segmentation=True,
        min_detection_confidence=0.2,
        min_tracking_confidence=0.2
    ) as pose:
        results = pose.process(image_rgb)
        
        # Get segmentation mask if enabled in MP (it's False in config above, but we can enable it or use external)
        # The user prompt said "Use OpenCV to convert... Calculate pixels inside Body Segmentation Mask".
        # We need a mask. `measure.py` has `segmentation_mask_mediapipe`.
        # Let's generate a mask here for quality check if MP pose segmentation is not enabled or to be sure.
        # Actually, `analyze_body` config has `enable_segmentation=False`. 
        # I should probably enable it or generate it separately.
        # Enabling it in `analyze_body` is cleanest.
        
        # WAIT: I can't easily change the `pose` context manager arguments without replacing the whole block.
        # And I don't want to break existing logic.
        # But `assess_image_quality` needs a mask for accurate skin detection.
        # I'll use `segmentation_mask_mediapipe` from `measure.py` (which uses Selfie Segmentation) 
        # OR just enable segmentation in Pose.
        
        # Let's try to use the existing `segmentation_mask_mediapipe` helper if available, 
        # or just run a quick segmentation if not.
        # Actually, I'll just enable segmentation in the Pose object I'm creating right here.
        pass
        print(f"DEBUG: Landmarks Detected? {bool(results.pose_landmarks)}")
        
        if not results.pose_landmarks:
            return {
                "body_fat_percentage": None,
                "waist_cm": None,
                "neck_cm": None,
                "annotated_image": annotated_img,
                "pixel_to_cm_ratio": None,
                "torso_volume_index": None,
                "landmarks_detected": False,
                "error": "Could not detect pose landmarks",
                "body_morphotype": None,
                "morphotype_description": None,
                "shoulder_to_waist_ratio": None,
                "posture_issues": [],
                "posture_good": [],
                "waist_to_hip_ratio": None,
                "health_risk_level": None,
                "hip_cm": None
            }
        
        landmarks = results.pose_landmarks.landmark
        
        # Draw skeleton
        if mp.solutions.drawing_utils:
            mp.solutions.drawing_utils.draw_landmarks(
                annotated_img,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS
            )
        
        # Extract key landmarks (MediaPipe Pose indices)
        # Nose: 0, Left Ear: 7, Right Ear: 8
        # Left Shoulder: 11, Right Shoulder: 12
        # Left Hip: 23, Right Hip: 24
        # Left Ankle: 27, Right Ankle: 28
        
        def get_landmark_xy(idx):

            if idx >= len(landmarks):
                return None
            lm = landmarks[idx]
            return (int(lm.x * w_img), int(lm.y * h_img))
        
        nose = get_landmark_xy(0)
        left_ear = get_landmark_xy(7)
        right_ear = get_landmark_xy(8)
        left_shoulder = get_landmark_xy(11)
        right_shoulder = get_landmark_xy(12)
        left_hip = get_landmark_xy(23)
        right_hip = get_landmark_xy(24)
        left_ankle = get_landmark_xy(27)
        right_ankle = get_landmark_xy(28)
        
        # Check if all required landmarks are visible
        required_landmarks = [nose, left_shoulder, right_shoulder, left_hip, right_hip, left_ankle, right_ankle]
        if any(lm is None for lm in required_landmarks):
            return {
                "body_fat_percentage": None,
                "waist_cm": None,
                "neck_cm": None,
                "annotated_image": annotated_img,
                "pixel_to_cm_ratio": None,
                "torso_volume_index": None,
                "landmarks_detected": False,
                "error": "Not all required landmarks detected",
                "body_morphotype": None,
                "morphotype_description": None,
                "shoulder_to_waist_ratio": None,
                "posture_issues": [],
                "posture_good": [],
                "waist_to_hip_ratio": None,
                "health_risk_level": None,
                "hip_cm": None
            }
        
        # Step 2: Calculate Pixel-to-CM Conversion (The Scale)
        # Use average ankle position for bottom reference
        avg_ankle_y = (left_ankle[1] + right_ankle[1]) / 2
        person_pixel_height = abs(nose[1] - avg_ankle_y)
        
        if person_pixel_height <= 0:
            return {
                "body_fat_percentage": None,
                "waist_cm": None,
                "neck_cm": None,
                "annotated_image": annotated_img,
                "pixel_to_cm_ratio": None,
                "torso_volume_index": None,
                "landmarks_detected": False,
                "error": "Invalid height measurement",
                "body_morphotype": None,
                "morphotype_description": None,
                "shoulder_to_waist_ratio": None,
                "posture_issues": [],
                "posture_good": [],
                "waist_to_hip_ratio": None,
                "health_risk_level": None,
                "hip_cm": None
            }
        
        pixel_to_cm_ratio = user_height_cm / person_pixel_height
        
        # Step 3: Extract Measurements (in Pixels)
        # Shoulder Width: Distance between Left Shoulder and Right Shoulder
        shoulder_width_px = math.sqrt(
            (right_shoulder[0] - left_shoulder[0]) ** 2 + 
            (right_shoulder[1] - left_shoulder[1]) ** 2
        )
        
        # Waist Width: Distance between Left Hip and Right Hip
        waist_width_px = math.sqrt(
            (right_hip[0] - left_hip[0]) ** 2 + 
            (right_hip[1] - left_hip[1]) ** 2
        )
        
        # Hip Width: Same as waist for now (can be refined with additional landmarks)
        hip_width_px = waist_width_px
        
        # Convert waist width to circumference (approximate)
        # For a 2D projection, multiply by a factor to approximate 3D circumference
        # Using factor of 2.5 for a flattened ellipse approximation
        waist_circumference_px = waist_width_px * 2.5
        hip_circumference_px = hip_width_px * 2.5
        
        # Neck Width: Estimate based on shoulder width
        # Neck is typically about 30-35% of shoulder width
        neck_width_px = shoulder_width_px * 0.32
        neck_circumference_px = neck_width_px * math.pi  # Approximate as circle
        
        # Step 4: Calculate Real Metrics (in cm)
        waist_cm = waist_circumference_px * pixel_to_cm_ratio
        hip_cm = hip_circumference_px * pixel_to_cm_ratio
        neck_cm = neck_circumference_px * pixel_to_cm_ratio
        shoulder_width_cm = shoulder_width_px * pixel_to_cm_ratio
        waist_width_cm = waist_width_px * pixel_to_cm_ratio
        
        # Step 5: Body Fat Formula (US Navy Method)
        # Formula: Body Fat % = 495 / (1.0324 - 0.19077 * log10(waist - neck) + 0.15456 * log10(height)) - 450
        body_fat_pct = None
        try:
            waist_neck_diff = waist_cm - neck_cm
            if waist_neck_diff > 0 and user_height_cm > 0:
                log_waist_neck = math.log10(waist_neck_diff)
                log_height = math.log10(user_height_cm)
                
                denominator = 1.0324 - 0.19077 * log_waist_neck + 0.15456 * log_height
                if denominator > 0:
                    body_fat_pct = (495 / denominator) - 450
                    # Clamp to reasonable range
                    body_fat_pct = max(0.0, min(50.0, body_fat_pct))
        except (ValueError, ZeroDivisionError) as e:
            print(f"Body fat calculation error: {e}")
            body_fat_pct = None
        
        # Step 6: Torso Volume Index (Bonus)
        # Calculate shoulder-to-hip distance
        avg_shoulder_y = (left_shoulder[1] + right_shoulder[1]) / 2
        avg_hip_y = (left_hip[1] + right_hip[1]) / 2
        shoulder_hip_distance_px = abs(avg_shoulder_y - avg_hip_y)
        shoulder_hip_distance_cm = shoulder_hip_distance_px * pixel_to_cm_ratio
        
        # Volume = Waist_Width * Shoulder_To_Hip_Distance (treating as cylinder)
        torso_volume_cm3 = waist_cm * shoulder_hip_distance_cm
        
        # Normalize to score (1-100) - heuristic based on typical ranges
        # Typical torso volume for adults: 5000-15000 cm³
        # Normalize: (volume - min) / (max - min) * 100
        min_volume = 3000
        max_volume = 20000
        torso_volume_index = ((torso_volume_cm3 - min_volume) / (max_volume - min_volume)) * 100
        torso_volume_index = max(1.0, min(100.0, torso_volume_index))
        
        # ========== NEW FEATURES ==========
        
        # 1. Body Morphotype Detection (Somatotype)
        # Calculate Shoulder-to-Waist Ratio
        shoulder_to_waist_ratio = shoulder_width_cm / waist_width_cm if waist_width_cm > 0 else 0
        
        if shoulder_to_waist_ratio > 1.4:
            body_morphotype = "Mesomorph"
            morphotype_description = "Athletic/Muscular"
        elif shoulder_to_waist_ratio < 1.1:
            body_morphotype = "Endomorph"
            morphotype_description = "Higher fat storage"
        else:  # Between 1.1 - 1.4
            body_morphotype = "Ectomorph"
            morphotype_description = "Lean/Average"
        
        # 2. Static Posture Analysis
        posture_issues = []
        posture_good = []
        
        # Shoulder Imbalance Check
        shoulder_y_diff = abs(left_shoulder[1] - right_shoulder[1])
        shoulder_y_diff_cm = shoulder_y_diff * pixel_to_cm_ratio
        height_threshold = user_height_cm * 0.02  # 2% of height
        
        if shoulder_y_diff_cm > height_threshold:
            posture_issues.append("Uneven Shoulders")
            shoulder_imbalance_detected = True
        else:
            posture_good.append("Balanced Shoulders")
            shoulder_imbalance_detected = False
        
        # Forward Head Posture (Text Neck) Check
        forward_head_detected = False
        if left_ear and right_ear and left_shoulder and right_shoulder:
            avg_ear_x = (left_ear[0] + right_ear[0]) / 2
            avg_shoulder_x = (left_shoulder[0] + right_shoulder[0]) / 2
            ear_forward_offset = avg_ear_x - avg_shoulder_x
            ear_forward_offset_cm = abs(ear_forward_offset) * pixel_to_cm_ratio
            
            # Threshold: if ear is more than 3cm forward of shoulder line, flag it
            forward_threshold_cm = 3.0
            if ear_forward_offset_cm > forward_threshold_cm:
                posture_issues.append("Forward Head Posture")
                forward_head_detected = True
            else:
                posture_good.append("Good Head Position")
        
        # 3. Health Risk Indicator (Waist-to-Hip Ratio - WHR)
        whr = waist_cm / hip_cm if hip_cm > 0 else 0
        if whr < 0.9:
            health_risk_level = "Low Risk"
            health_risk_color = (0, 255, 0)  # Green
        else:
            health_risk_level = "High Risk"
            health_risk_color = (0, 0, 255)  # Red
            
        # 4. Image Quality Assessment
        # Get segmentation mask from results
        seg_mask = None
        if results.segmentation_mask is not None:
             seg_mask = (results.segmentation_mask.numpy_view() * 255).astype(np.uint8)
        
        quality_result = assess_image_quality(image, landmarks, seg_mask)
        
        # 5. Visual Output (Cyberpunk Style)
        # Triangle: Left Shoulder -> Right Shoulder -> Left Hip -> Right Hip -> Left Shoulder
        triangle_points = np.array([
            [left_shoulder[0], left_shoulder[1]],
            [right_shoulder[0], right_shoulder[1]],
            [right_hip[0], right_hip[1]],
            [left_hip[0], left_hip[1]]
        ], np.int32)
        cv2.polylines(annotated_img, [triangle_points], True, neon_blue, 2)
        # Fill with semi-transparent overlay
        overlay = annotated_img.copy()
        cv2.fillPoly(overlay, [triangle_points], neon_blue)
        cv2.addWeighted(overlay, 0.15, annotated_img, 0.85, 0, annotated_img)
        
        # Posture Visual Indicators
        if shoulder_imbalance_detected:
            # Draw Red Alert Lines on shoulders
            cv2.line(annotated_img, left_shoulder, right_shoulder, red_alert, thick_thickness)
            # Draw warning symbol
            alert_x = (left_shoulder[0] + right_shoulder[0]) // 2
            alert_y = (left_shoulder[1] + right_shoulder[1]) // 2 - 30
            cv2.putText(annotated_img, "!", (alert_x, alert_y), 
                       font, 1.5, red_alert, 3)
        else:
            # Draw Green Checkmark for good shoulder alignment
            check_x = (left_shoulder[0] + right_shoulder[0]) // 2
            check_y = (left_shoulder[1] + right_shoulder[1]) // 2 - 30
            # Simple checkmark using lines
            cv2.line(annotated_img, (check_x - 10, check_y), (check_x, check_y + 10), neon_green, 3)
            cv2.line(annotated_img, (check_x, check_y + 10), (check_x + 15, check_y - 10), neon_green, 3)
        
        if forward_head_detected:
            # Draw red line from ear to shoulder
            if left_ear and left_shoulder:
                avg_ear_pos = ((left_ear[0] + right_ear[0]) // 2, (left_ear[1] + right_ear[1]) // 2)
                avg_shoulder_pos = ((left_shoulder[0] + right_shoulder[0]) // 2, 
                                   (left_shoulder[1] + right_shoulder[1]) // 2)
                cv2.line(annotated_img, avg_ear_pos, avg_shoulder_pos, red_alert, 2)
                cv2.putText(annotated_img, "Forward Head", 
                           (avg_ear_pos[0] - 50, avg_ear_pos[1] - 10), 
                           font, 0.5, red_alert, 2)
        else:
            # Draw green checkmark for good head position
            if left_ear:
                check_x = (left_ear[0] + right_ear[0]) // 2
                check_y = (left_ear[1] + right_ear[1]) // 2 - 20
                cv2.line(annotated_img, (check_x - 8, check_y), (check_x, check_y + 8), neon_green, 2)
                cv2.line(annotated_img, (check_x, check_y + 8), (check_x + 12, check_y - 8), neon_green, 2)
        
        # Draw waist line (between hips)
        cv2.line(annotated_img, left_hip, right_hip, neon_green, 3)
        waist_mid_x = (left_hip[0] + right_hip[0]) // 2
        waist_mid_y = (left_hip[1] + right_hip[1]) // 2
        cv2.putText(annotated_img, f"Waist: {waist_cm:.1f} cm", 
                   (waist_mid_x - 80, waist_mid_y - 10), 
                   font, font_scale, neon_green, thickness)
        
        # Draw neck line (estimated from shoulders)
        neck_y = int((left_shoulder[1] + right_shoulder[1]) / 2 - shoulder_width_px * 0.15)
        neck_left_x = int((left_shoulder[0] + right_shoulder[0]) / 2 - neck_width_px / 2)
        neck_right_x = int((left_shoulder[0] + right_shoulder[0]) / 2 + neck_width_px / 2)
        neck_left = (neck_left_x, neck_y)
        neck_right = (neck_right_x, neck_y)
        cv2.line(annotated_img, neck_left, neck_right, neon_green, 3)
        cv2.putText(annotated_img, f"Neck: {neck_cm:.1f} cm", 
                   (neck_left_x, neck_y - 10), 
                   font, font_scale, neon_green, thickness)
        
        # Draw height line (from nose to ankle)
        avg_ankle_x = int((left_ankle[0] + right_ankle[0]) / 2)
        cv2.line(annotated_img, nose, (avg_ankle_x, int(avg_ankle_y)), cyan, 2)
        height_mid_x = (nose[0] + avg_ankle_x) // 2
        height_mid_y = (nose[1] + int(avg_ankle_y)) // 2
        cv2.putText(annotated_img, f"Height: {user_height_cm} cm", 
                   (height_mid_x - 60, height_mid_y), 
                   font, font_scale, cyan, thickness)
        
        # Draw key landmarks
        for point in [nose, left_shoulder, right_shoulder, left_hip, right_hip, left_ankle, right_ankle]:
            cv2.circle(annotated_img, point, 5, (255, 0, 255), -1)
        
        # Add body fat percentage text at top
        y_offset = 30
        if body_fat_pct is not None:
            bf_text = f"Body Fat: {body_fat_pct:.1f}%"
            text_size = cv2.getTextSize(bf_text, font, 1.0, 2)[0]
            text_x = (w_img - text_size[0]) // 2
            cv2.putText(annotated_img, bf_text, (text_x, y_offset), 
                       font, 1.0, neon_green, 2)
            y_offset += 35
        
        # Add torso volume index
        volume_text = f"Torso Volume Index: {torso_volume_index:.0f}/100"
        text_size = cv2.getTextSize(volume_text, font, 0.7, 2)[0]
        text_x = (w_img - text_size[0]) // 2
        cv2.putText(annotated_img, volume_text, (text_x, y_offset), 
                   font, 0.7, cyan, 2)
        y_offset += 30
        
        # Add Body Morphotype
        morphotype_text = f"Body Type: {body_morphotype} ({morphotype_description})"
        text_size = cv2.getTextSize(morphotype_text, font, 0.7, 2)[0]
        text_x = (w_img - text_size[0]) // 2
        cv2.putText(annotated_img, morphotype_text, (text_x, y_offset), 
                   font, 0.7, neon_blue, 2)
        y_offset += 30
        
        # Add Waist-to-Hip Ratio and Health Risk
        whr_text = f"WHR: {whr:.2f} - {health_risk_level}"
        text_size = cv2.getTextSize(whr_text, font, 0.7, 2)[0]
        text_x = (w_img - text_size[0]) // 2
        cv2.putText(annotated_img, whr_text, (text_x, y_offset), 
                   font, 0.7, health_risk_color, 2)
        y_offset += 30
        
        # Add Posture Analysis Results
        if posture_issues:
            posture_text = "Posture Issues: " + ", ".join(posture_issues)
            text_size = cv2.getTextSize(posture_text, font, 0.6, 2)[0]
            text_x = (w_img - text_size[0]) // 2
            cv2.putText(annotated_img, posture_text, (text_x, y_offset), 
                       font, 0.6, red_alert, 2)
            y_offset += 25
        
        if posture_good:
            posture_text = "Good: " + ", ".join(posture_good)
            text_size = cv2.getTextSize(posture_text, font, 0.6, 2)[0]
            text_x = (w_img - text_size[0]) // 2
            cv2.putText(annotated_img, posture_text, (text_x, y_offset), 
                       font, 0.6, neon_green, 2)
    
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
        "morphotype_description": morphotype_description,
        "shoulder_to_waist_ratio": round(shoulder_to_waist_ratio, 2),
        "posture_issues": posture_issues,
        "posture_good": posture_good,
        "waist_to_hip_ratio": round(whr, 2),
        "health_risk_level": health_risk_level,
        "hip_cm": round(hip_cm, 1),
        "scan_quality": quality_result
    }
