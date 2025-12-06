from __future__ import annotations

import random
from typing import List, Dict, Optional

exercise_database: List[Dict[str, str]] = [
    {"name": "Burpees", "category": "HIIT", "target_muscle": "Full Body", "difficulty": "Intermediate", "environment": "Home"},
    {"name": "Jumping Jacks", "category": "Cardio", "target_muscle": "Full Body", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Mountain Climbers", "category": "HIIT", "target_muscle": "Core", "difficulty": "Intermediate", "environment": "Home"},
    {"name": "High Knees", "category": "Cardio", "target_muscle": "Legs", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Jump Rope Sprints", "category": "Cardio", "target_muscle": "Full Body", "difficulty": "Intermediate", "environment": "Home"},
    {"name": "Sprint Intervals", "category": "Cardio", "target_muscle": "Legs", "difficulty": "Advanced", "environment": "Outdoor"},
    {"name": "Cycling HIIT", "category": "Cardio", "target_muscle": "Legs", "difficulty": "Intermediate", "environment": "Gym"},
    {"name": "Rowing Machine Intervals", "category": "Cardio", "target_muscle": "Back", "difficulty": "Intermediate", "environment": "Gym"},
    {"name": "Battle Rope Slams", "category": "HIIT", "target_muscle": "Shoulders", "difficulty": "Intermediate", "environment": "Gym"},
    {"name": "Kettlebell Swings", "category": "Strength", "target_muscle": "Glutes", "difficulty": "Intermediate", "environment": "Home"},
    {"name": "Push-Ups", "category": "Strength", "target_muscle": "Chest", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Diamond Push-Ups", "category": "Strength", "target_muscle": "Triceps", "difficulty": "Intermediate", "environment": "Home"},
    {"name": "Pike Push-Ups", "category": "Strength", "target_muscle": "Shoulders", "difficulty": "Advanced", "environment": "Home"},
    {"name": "Pull-Ups", "category": "Strength", "target_muscle": "Back", "difficulty": "Advanced", "environment": "Gym"},
    {"name": "Chin-Ups", "category": "Strength", "target_muscle": "Back", "difficulty": "Intermediate", "environment": "Gym"},
    {"name": "TRX Rows", "category": "Strength", "target_muscle": "Back", "difficulty": "Intermediate", "environment": "Gym"},
    {"name": "Barbell Bench Press", "category": "Strength", "target_muscle": "Chest", "difficulty": "Intermediate", "environment": "Gym"},
    {"name": "Dumbbell Chest Fly", "category": "Strength", "target_muscle": "Chest", "difficulty": "Intermediate", "environment": "Gym"},
    {"name": "Barbell Back Squat", "category": "Strength", "target_muscle": "Legs", "difficulty": "Advanced", "environment": "Gym"},
    {"name": "Front Squat", "category": "Strength", "target_muscle": "Legs", "difficulty": "Advanced", "environment": "Gym"},
    {"name": "Bulgarian Split Squat", "category": "Strength", "target_muscle": "Legs", "difficulty": "Intermediate", "environment": "Home"},
    {"name": "Walking Lunges", "category": "Strength", "target_muscle": "Legs", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Conventional Deadlift", "category": "Strength", "target_muscle": "Posterior Chain", "difficulty": "Advanced", "environment": "Gym"},
    {"name": "Romanian Deadlift", "category": "Strength", "target_muscle": "Hamstrings", "difficulty": "Intermediate", "environment": "Gym"},
    {"name": "Hip Thrusts", "category": "Strength", "target_muscle": "Glutes", "difficulty": "Intermediate", "environment": "Gym"},
    {"name": "Glute Bridges", "category": "Strength", "target_muscle": "Glutes", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Forearm Plank", "category": "Core", "target_muscle": "Abs", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Side Plank", "category": "Core", "target_muscle": "Obliques", "difficulty": "Intermediate", "environment": "Home"},
    {"name": "Hollow Body Hold", "category": "Core", "target_muscle": "Abs", "difficulty": "Intermediate", "environment": "Home"},
    {"name": "Russian Twists", "category": "Core", "target_muscle": "Obliques", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Hanging Leg Raises", "category": "Core", "target_muscle": "Abs", "difficulty": "Advanced", "environment": "Gym"},
    {"name": "Bicycle Crunches", "category": "Core", "target_muscle": "Abs", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Standing Shoulder Press", "category": "Strength", "target_muscle": "Shoulders", "difficulty": "Intermediate", "environment": "Gym"},
    {"name": "Arnold Press", "category": "Strength", "target_muscle": "Shoulders", "difficulty": "Intermediate", "environment": "Gym"},
    {"name": "Lateral Raises", "category": "Strength", "target_muscle": "Shoulders", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Face Pulls", "category": "Strength", "target_muscle": "Upper Back", "difficulty": "Beginner", "environment": "Gym"},
    {"name": "Banded Pull-Aparts", "category": "Strength", "target_muscle": "Upper Back", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Farmer's Carry", "category": "Strength", "target_muscle": "Grip", "difficulty": "Intermediate", "environment": "Gym"},
    {"name": "Sled Push", "category": "HIIT", "target_muscle": "Full Body", "difficulty": "Advanced", "environment": "Gym"},
    {"name": "Medicine Ball Slams", "category": "HIIT", "target_muscle": "Core", "difficulty": "Intermediate", "environment": "Gym"},
    {"name": "Jump Squats", "category": "Plyometrics", "target_muscle": "Legs", "difficulty": "Intermediate", "environment": "Home"},
    {"name": "Box Jumps", "category": "Plyometrics", "target_muscle": "Legs", "difficulty": "Intermediate", "environment": "Gym"},
    {"name": "Kettlebell Goblet Squat", "category": "Strength", "target_muscle": "Legs", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Resistance Band Rows", "category": "Strength", "target_muscle": "Back", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Yoga Sun Salutation", "category": "Flexibility", "target_muscle": "Full Body", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Cat-Cow Flow", "category": "Flexibility", "target_muscle": "Spine", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Downward Dog Flow", "category": "Flexibility", "target_muscle": "Hamstrings", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Pilates Hundred", "category": "Flexibility", "target_muscle": "Core", "difficulty": "Intermediate", "environment": "Home"},
    {"name": "Single-Leg Bodyweight RDL", "category": "Strength", "target_muscle": "Hamstrings", "difficulty": "Intermediate", "environment": "Home"},
    {"name": "Stair Climber Session", "category": "Cardio", "target_muscle": "Legs", "difficulty": "Intermediate", "environment": "Gym"},
    {"name": "Wall Pushups", "category": "Strength", "target_muscle": "Chest", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Chair Squats", "category": "Strength", "target_muscle": "Legs", "difficulty": "Beginner", "environment": "Home"},
    {"name": "Swimming", "category": "Cardio", "target_muscle": "Full Body", "difficulty": "Beginner", "environment": "Pool"},
    {"name": "Water Aerobics", "category": "Cardio", "target_muscle": "Full Body", "difficulty": "Beginner", "environment": "Pool"},
    {"name": "Seated Leg Lifts", "category": "Strength", "target_muscle": "Legs", "difficulty": "Beginner", "environment": "Home"},
]


def _filter_exercises(*categories: str, difficulty: Optional[str] = None) -> List[Dict[str, str]]:
    cats = {c.lower() for c in categories}
    result = []
    for exercise in exercise_database:
        if cats and exercise["category"].lower() not in cats:
            continue
        if difficulty and exercise["difficulty"].lower() != difficulty.lower():
            continue
        result.append(exercise)
    return result


def _mix_home_and_gym(exercises: List[Dict[str, str]], limit: int) -> List[Dict[str, str]]:
    random.shuffle(exercises)
    home = [e for e in exercises if e["environment"].lower() != "gym"]
    gym = [e for e in exercises if e["environment"].lower() == "gym"]
    plan: List[Dict[str, str]] = []

    while exercises and len(plan) < limit:
        target_pool = home if len(plan) % 2 == 0 else gym
        if not target_pool:
            target_pool = gym if target_pool is home else home
        if not target_pool:
            break
        plan.append(target_pool.pop())
    return plan


def get_recommended_workouts(body_fat_percentage: float, current_waist_size: Optional[float], plan_size: int = 6, age: int = 30) -> List[Dict[str, str]]:
    """Return a workout plan tailored to the estimated body composition and age."""

    high_body_fat = body_fat_percentage >= 30 or (body_fat_percentage >= 25 and (current_waist_size or 0) >= 90)
    low_body_fat = body_fat_percentage <= 15
    is_senior = age >= 50

    if high_body_fat:
        pool = _filter_exercises("Cardio", "HIIT", "Plyometrics")
    elif low_body_fat:
        pool = _filter_exercises("Strength")
    else:
        pool = _filter_exercises("Strength", "Core", "Flexibility")

    # Age-Adaptive Filtering
    if is_senior:
        # Filter out high impact
        high_impact_keywords = ["Jump", "Sprint", "Burpee", "Box", "Sled", "Slams", "Battle Rope", "High Knees"]
        safe_pool = []
        for ex in pool:
            if any(k in ex["name"] for k in high_impact_keywords):
                continue
            # Add senior friendly flag
            ex_copy = ex.copy()
            ex_copy["is_senior_friendly"] = True
            safe_pool.append(ex_copy)
        
        # If pool is too small, add specific senior exercises
        if len(safe_pool) < plan_size:
            senior_additions = _filter_exercises("Flexibility") + [
                e for e in exercise_database if e["name"] in ["Wall Pushups", "Chair Squats", "Swimming", "Water Aerobics", "Seated Leg Lifts", "Walking Lunges"]
            ]
            for ex in senior_additions:
                ex_copy = ex.copy()
                ex_copy["is_senior_friendly"] = True
                if ex_copy not in safe_pool:
                    safe_pool.append(ex_copy)
        
        pool = safe_pool

    if len(pool) < plan_size:
        # Fallback if filtering was too aggressive
        pool = exercise_database.copy()

    return _mix_home_and_gym(pool, plan_size)


__all__ = ["exercise_database", "get_recommended_workouts"]

