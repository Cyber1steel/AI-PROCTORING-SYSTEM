import time
import uuid
import statistics


NOSE_TIP = 1
LEFT_EYE_OUTER = 33
RIGHT_EYE_OUTER = 263
FOREHEAD = 10
CHIN = 152

YAW_SCALE = 150    # empirical scale factor, ratio -> approx degrees
PITCH_SCALE = 130


def get_pose_ratios(landmarks, frame_width, frame_height):
    def pt(i):
        lm = landmarks[i]
        return (lm.x * frame_width, lm.y * frame_height)

    nose = pt(NOSE_TIP)
    left_eye = pt(LEFT_EYE_OUTER)
    right_eye = pt(RIGHT_EYE_OUTER)
    forehead = pt(FOREHEAD)
    chin = pt(CHIN)

    eye_mid_x = (left_eye[0] + right_eye[0]) / 2
    inter_eye_dist = abs(right_eye[0] - left_eye[0])
    yaw_ratio = (nose[0] - eye_mid_x) / inter_eye_dist if inter_eye_dist else 0

    face_mid_y = (forehead[1] + chin[1]) / 2
    face_height = abs(chin[1] - forehead[1])
    pitch_ratio = (nose[1] - face_mid_y) / face_height if face_height else 0

    return yaw_ratio * YAW_SCALE, pitch_ratio * PITCH_SCALE


def calibrate_head_pose(landmark_frames, frame_width, frame_height):
    """
    landmark_frames: landmarks collected during the instruction-guided
    calibration capture (student sits properly, looks at screen, clicks capture).
    Returns baseline dict, or None if no usable frames were captured.
    """
    yaws, pitches = [], []

    for landmarks in landmark_frames:
        if landmarks is None:
            continue
        yaw, pitch = get_pose_ratios(landmarks, frame_width, frame_height)
        yaws.append(yaw)
        pitches.append(pitch)

    if not yaws:
        return None

    yaw_center = statistics.median(yaws)
    pitch_center = statistics.median(pitches)

    yaw_spread = statistics.stdev(yaws) if len(yaws) > 1 else 0
    pitch_spread = statistics.stdev(pitches) if len(pitches) > 1 else 0

    return {
        "yaw_center": yaw_center,
        "pitch_center": pitch_center,
        "yaw_tolerance": 25 + max(yaw_spread, 2),
        "pitch_tolerance": 20 + max(pitch_spread, 2),
    }


def check_head_movement(
    landmarks,
    baseline,
    frame_width,
    frame_height,
    deviation_start_time,
    flagged,
    incident_id,
    threshold_seconds=4
):
    event = None

    if landmarks is None or baseline is None:
        # No face — absence detector already owns this case, just reset silently
        return None, None, False, None

    yaw, pitch = get_pose_ratios(landmarks, frame_width, frame_height)

    yaw_dev = abs(yaw - baseline["yaw_center"])
    pitch_dev = abs(pitch - baseline["pitch_center"])

    is_deviant = (
        yaw_dev > baseline["yaw_tolerance"]
        or pitch_dev > baseline["pitch_tolerance"]
    )

    if is_deviant:
        if deviation_start_time is None:
            deviation_start_time = time.time()
            incident_id = f"HM-{uuid.uuid4().hex[:6].upper()}"

        elapsed = time.time() - deviation_start_time

        if elapsed >= threshold_seconds and not flagged:
            direction = "left" if yaw > baseline["yaw_center"] else "right"
            if yaw_dev < pitch_dev:
                direction = "down" if pitch > baseline["pitch_center"] else "up"

            event = {
                "incident_id": incident_id,
                "event_type": "head_movement",
                "timestamp": time.strftime("%H:%M:%S"),
                "duration": round(elapsed, 1),
                "direction": direction
            }
            flagged = True
    else:
        deviation_start_time = None
        flagged = False
        incident_id = None

    return event, deviation_start_time, flagged, incident_id