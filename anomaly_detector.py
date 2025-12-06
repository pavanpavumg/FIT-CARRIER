from datetime import datetime

def check_anomaly(current_waist, history_records):
    """
    Checks for suspicious variance in waist measurement.
    
    Args:
        current_waist (float): The current waist measurement in cm.
        history_records (list): List of history dictionaries. 
                                Expected format: {"timestamp": datetime_obj, "waist_cm": float, ...}
                                
    Returns:
        dict: {"is_safe": bool, "message": str (optional)}
    """
    if not history_records:
        return {"is_safe": True}
        
    # Get the last recorded measurement
    # Assuming history_records are sorted by timestamp (oldest to newest) or we find the latest
    # The prompt implies we get the "last recorded", so we'll sort to be safe or assume the caller provides it.
    # However, app.py's get_history_for_user returns a list. 
    # Let's sort by timestamp descending to find the latest.
    
    valid_history = [r for r in history_records if r.get("waist_cm") is not None and r.get("timestamp")]
    
    if not valid_history:
        return {"is_safe": True}
        
    # Sort by timestamp descending (newest first)
    valid_history.sort(key=lambda x: x["timestamp"], reverse=True)
    last_record = valid_history[0]
    
    last_waist = last_record["waist_cm"]
    last_date = last_record["timestamp"]
    
    # Calculate % difference
    if last_waist == 0:
         return {"is_safe": True} # Avoid division by zero
         
    diff_percent = abs(current_waist - last_waist) / last_waist * 100
    
    # Calculate time difference
    # current_waist is from "now"
    now = datetime.now()
    
    # Ensure last_date is a datetime object
    if isinstance(last_date, str):
        try:
            last_date = datetime.fromisoformat(last_date)
        except ValueError:
             return {"is_safe": True} # Cannot parse date, skip check
             
    time_diff = (now - last_date).days
    
    # Rule: If difference > 15% AND time difference < 30 days
    if diff_percent > 15 and time_diff < 30:
        return {
            "is_safe": False, 
            "message": f"Suspicious variance detected. {diff_percent:.1f}% change in {time_diff} days."
        }
        
    return {"is_safe": True}
