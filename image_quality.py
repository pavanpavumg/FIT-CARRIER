import cv2
import numpy as np

def assess_image_quality(image, landmarks, segmentation_mask=None):
    """
    Assess the quality of the image for body analysis based on skin ratio and pose facing.

    Args:
        image: BGR image (numpy array).
        landmarks: List of MediaPipe pose landmarks.
        segmentation_mask: Optional binary mask (uint8) where 255 is body, 0 is background.

    Returns:
        dict: {
            "score": "High Accuracy" | "Fair" | "Low Accuracy",
            "color": "green" | "yellow" | "red",
            "message": "Description of the quality assessment",
            "skin_ratio": float,
            "is_front_view": bool
        }
    """
    h, w = image.shape[:2]
    
    # --- 1. Detect Skin Ratio (Shirtless Check) ---
    skin_ratio = 0.0
    
    # Convert to HSV
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # Define skin tone range (Standard generic range, can be tuned)
    # Lower: (0, 20, 70), Upper: (20, 255, 255) covers most skin tones
    lower_skin = np.array([0, 20, 70], dtype=np.uint8)
    upper_skin = np.array([20, 255, 255], dtype=np.uint8)
    
    skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
    
    # If we have a body segmentation mask, only count skin pixels INSIDE the body
    if segmentation_mask is not None:
        # Ensure mask is same size
        if segmentation_mask.shape[:2] != (h, w):
            segmentation_mask = cv2.resize(segmentation_mask, (w, h))
            
        # Combine skin mask with body mask
        combined_mask = cv2.bitwise_and(skin_mask, skin_mask, mask=segmentation_mask)
        
        # Calculate ratio: Skin Pixels / Total Body Pixels
        body_pixels = cv2.countNonZero(segmentation_mask)
        skin_pixels = cv2.countNonZero(combined_mask)
        
        if body_pixels > 0:
            skin_ratio = (skin_pixels / body_pixels) * 100
        else:
            skin_ratio = 0
    else:
        # Fallback: Calculate ratio relative to entire image (less accurate)
        skin_pixels = cv2.countNonZero(skin_mask)
        total_pixels = w * h
        skin_ratio = (skin_pixels / total_pixels) * 100

    # --- 2. Detect Pose Facing (Front vs Back) ---
    # Landmarks: Nose (0), Left Ear (7), Right Ear (8), Shoulders (11, 12)
    nose = landmarks[0]
    left_ear = landmarks[7]
    right_ear = landmarks[8]
    
    is_front_view = True
    facing_message = ""
    
    # Check visibility
    if nose.visibility < 0.5:
        is_front_view = False
        facing_message = "Nose not clearly visible."
    else:
        # Check Z-depth (if available and reliable) or relative position
        # In MP Pose, Z is relative to hip center. Negative Z is closer to camera.
        # If Nose Z > Ear Z, nose is further away -> Back view? 
        # Actually, for front view, Nose Z should be < Ear Z (closer to camera).
        
        # Let's use the user's rule: "If the Nose is not visible or is behind the ears"
        # "Behind" means larger Z value in MP coordinates (usually).
        # However, 2D projection check might be safer if Z is noisy.
        # If nose is strictly between ears in X, it's likely front or back.
        # If back view, ears might be visible but nose hidden or "behind" (occluded).
        
        # Using Z values from landmarks
        if nose.z > left_ear.z and nose.z > right_ear.z:
             is_front_view = False
             facing_message = "Back view detected (Nose behind ears)."
    
    # --- 3. Determine Quality Score ---
    score = "Fair"
    color = "yellow"
    message = "Average quality."
    
    if not is_front_view:
        score = "Poor"
        color = "red"
        message = "Back view detected. Results may vary."
    else:
        if skin_ratio > 30:
            score = "High Accuracy"
            color = "green"
            message = "Perfect conditions (Tight clothes/Skin)."
        elif skin_ratio < 10:
            score = "Low Accuracy"
            color = "red" # Or yellow? User said "Low Accuracy - Loose Clothing Detected"
            # User logic: 
            # > 30% -> High Accuracy
            # < 10% -> Low Accuracy
            # Between 10-30% -> Fair (implied)
            message = "Loose clothing detected. Measurements may be less accurate."
        else:
            score = "Fair"
            color = "yellow"
            message = "Fair quality. T-shirt detected."

    return {
        "score": score,
        "color": color,
        "message": message,
        "skin_ratio": round(skin_ratio, 1),
        "is_front_view": is_front_view
    }
