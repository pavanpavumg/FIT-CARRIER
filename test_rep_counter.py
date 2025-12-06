from rep_counter import RepCounter


def simulate_angles(up_angle, down_angle, frames_per_phase, reps):
    angles = []
    for _ in range(reps):
        angles += [up_angle] * frames_per_phase
        angles += [down_angle] * frames_per_phase
        angles += [up_angle] * frames_per_phase
    return angles


def test_counts_two_reps():
    rc = RepCounter(up_angle=160, down_angle=70, smoothing=3, min_time_frames=4)
    angles = simulate_angles(up_angle=165, down_angle=60, frames_per_phase=6, reps=2)
    for a in angles:
        rc.update(a)
    assert rc.count == 2


def test_reset_works():
    rc = RepCounter()
    angles = simulate_angles(165, 60, 4, 1)
    for a in angles:
        rc.update(a)
    assert rc.count >= 0
    rc.reset()
    assert rc.count == 0
