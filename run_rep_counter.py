from rep_counter import RepCounter

def simulate_reps(counter, up_angle=170, down_angle=60, frames_per_phase=8, reps=2):
    # Start at up position
    angles = []
    for _ in range(reps):
        # stay up
        angles += [up_angle] * frames_per_phase
        # move down
        angles += [down_angle] * frames_per_phase
        # move up
        angles += [up_angle] * frames_per_phase
    return angles

def main():
    rc = RepCounter(up_angle=160, down_angle=70, smoothing=3, min_time_frames=4)
    angles = simulate_reps(rc, up_angle=165, down_angle=60, frames_per_phase=6, reps=2)
    for i, a in enumerate(angles, 1):
        count = rc.update(a)
        print(f"Frame {i:03d}: angle={a:3d}, count={count}, state={rc.state}")

    print("Final count:", rc.count)

if __name__ == '__main__':
    main()
