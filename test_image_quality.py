import cv2
import numpy as np
from image_quality import assess_image_quality
from collections import namedtuple

# Mock Landmark class
Landmark = namedtuple("Landmark", ["x", "y", "z", "visibility"])

def create_mock_landmarks(is_front=True):
    # Nose, Left Ear, Right Ear, Left Shoulder, Right Shoulder
    # Indices: 0, 7, 8, 11, 12
    
    # Basic layout
    nose = Landmark(0.5, 0.2, -0.5 if is_front else 0.5, 0.9)
    l_ear = Landmark(0.55, 0.2, 0.0, 0.9)
    r_ear = Landmark(0.45, 0.2, 0.0, 0.9)
    l_shoulder = Landmark(0.6, 0.4, 0.0, 0.9)
    r_shoulder = Landmark(0.4, 0.4, 0.0, 0.9)
    
    # Fill others with dummy
    landmarks = [Landmark(0,0,0,0)] * 33
    landmarks[0] = nose
    landmarks[7] = l_ear
    landmarks[8] = r_ear
    landmarks[11] = l_shoulder
    landmarks[12] = r_shoulder
    
    return landmarks

def create_mock_image_and_mask(skin_ratio_percent):
    h, w = 100, 100
    image = np.zeros((h, w, 3), dtype=np.uint8)
    mask = np.zeros((h, w), dtype=np.uint8)
    
    # Fill mask (body) - let's say 50% of image is body
    cv2.rectangle(mask, (25, 25), (75, 75), 255, -1)
    body_pixels = 50 * 50
    
    # Calculate skin pixels needed
    skin_pixels_needed = int(body_pixels * (skin_ratio_percent / 100))
    
    # Draw skin color (HSV: 10, 150, 200 -> BGR approx)
    # OpenCV HSV range: H: 0-179, S: 0-255, V: 0-255
    # Skin color: H=10, S=100, V=200
    skin_color_hsv = np.array([[[10, 100, 200]]], dtype=np.uint8)
    skin_color_bgr = cv2.cvtColor(skin_color_hsv, cv2.COLOR_HSV2BGR)[0][0]
    skin_color_bgr = (int(skin_color_bgr[0]), int(skin_color_bgr[1]), int(skin_color_bgr[2]))
    
    # Draw skin on image inside the mask
    # We'll just draw a rectangle of the needed area
    # sqrt(skin_pixels)
    side = int(np.sqrt(skin_pixels_needed))
    if side > 0:
        cv2.rectangle(image, (25, 25), (25+side, 25+side), skin_color_bgr, -1)
        
    return image, mask

def test_quality_assessment():
    print("Running Image Quality Assessment Tests...\n")
    
    # Test 1: High Accuracy (Front, >30% Skin)
    print("Test 1: Front View, 40% Skin (Expect High Accuracy/Green)")
    lm = create_mock_landmarks(is_front=True)
    img, mask = create_mock_image_and_mask(40)
    res = assess_image_quality(img, lm, mask)
    print(f"Result: {res['score']} ({res['color']}) - {res['message']}")
    assert res['color'] == 'green'
    print("PASS\n")
    
    # Test 2: Low Accuracy (Front, 5% Skin)
    print("Test 2: Front View, 5% Skin (Expect Low Accuracy/Red)")
    lm = create_mock_landmarks(is_front=True)
    img, mask = create_mock_image_and_mask(5)
    res = assess_image_quality(img, lm, mask)
    print(f"Result: {res['score']} ({res['color']}) - {res['message']}")
    assert res['color'] == 'red'
    print("PASS\n")
    
    # Test 3: Back View (Nose behind ears)
    print("Test 3: Back View (Expect Poor/Red)")
    lm = create_mock_landmarks(is_front=False)
    img, mask = create_mock_image_and_mask(40) # Skin doesn't matter
    res = assess_image_quality(img, lm, mask)
    print(f"Result: {res['score']} ({res['color']}) - {res['message']}")
    assert res['score'] == 'Poor'
    print("PASS\n")
    
    print("All tests passed!")

if __name__ == "__main__":
    test_quality_assessment()
