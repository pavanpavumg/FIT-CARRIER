# rep_counter.py
from collections import deque

class RepCounter:
    def __init__(self, up_angle=160, down_angle=70, smoothing=5, min_time_frames=6):
        self.up_angle = up_angle
        self.down_angle = down_angle
        self.state = "UP"
        self.count = 0
        self.angle_buf = deque(maxlen=smoothing)
        self.min_time_frames = min_time_frames
        self.frame_since_transition = 0

    def _smoothed_angle(self, angle):
        self.angle_buf.append(angle)
        return sum(self.angle_buf)/len(self.angle_buf)

    def update(self, angle):
        sm_angle = self._smoothed_angle(angle)
        self.frame_since_transition += 1
        if self.state == "UP":
            if sm_angle < self.down_angle and self.frame_since_transition >= self.min_time_frames:
                self.state = "DOWN"
                self.frame_since_transition = 0
        elif self.state == "DOWN":
            if sm_angle > self.up_angle and self.frame_since_transition >= self.min_time_frames:
                self.state = "UP"
                self.count += 1
                self.frame_since_transition = 0
        return self.count

    def reset(self):
        self.state = "UP"
        self.count = 0
        self.angle_buf.clear()
        self.frame_since_transition = 0
