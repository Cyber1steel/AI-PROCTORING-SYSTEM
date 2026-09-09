import time

from .face_detection import detect_faces
from .absence_detection import check_absence
from .multiple_faces import check_multiple_faces
from .head_movement import check_head_movement, calibrate_head_pose

CALIBRATION_DURATION = 4  # seconds


class ProctoringEngine:

    def __init__(self):
        # Absence state
        self.absence_start_time = None
        self.absence_next_report_time = None
        self.absence_incident_id = None

        # Multiple-face state
        self.multi_face_start_time = None
        self.multi_face_flagged = False
        self.multi_face_incident_id = None

        # Head movement state
        self.head_pose_baseline = None
        self.head_deviation_start_time = None
        self.head_flagged = False
        self.head_incident_id = None

        self._calibrating = False
        self._calibration_start_time = None
        self._calibration_frames = []

        # All events generated during the session
        self.event_history = []

    def start_calibration(self):
        """Call this when the student clicks the calibration/capture button."""
        self._calibrating = True
        self._calibration_start_time = time.time()
        self._calibration_frames = []

    def process_frame(self, frame):
        num_faces, faces = detect_faces(frame)
        landmarks = faces[0].landmark if faces else None
        frame_height, frame_width = frame.shape[:2]

        calibration_done_this_frame = False

        if self._calibrating:
            self._calibration_frames.append(landmarks)
            if time.time() - self._calibration_start_time >= CALIBRATION_DURATION:
                self.head_pose_baseline = calibrate_head_pose(
                    self._calibration_frames, frame_width, frame_height
                )
                self._calibrating = False
                calibration_done_this_frame = True

        (
            absence_event,
            self.absence_start_time,
            self.absence_next_report_time,
            self.absence_incident_id
        ) = check_absence(
            num_faces,
            self.absence_start_time,
            self.absence_next_report_time,
            self.absence_incident_id
        )

        (
            multi_event,
            self.multi_face_start_time,
            self.multi_face_flagged,
            self.multi_face_incident_id
        ) = check_multiple_faces(
            num_faces,
            self.multi_face_start_time,
            self.multi_face_flagged,
            self.multi_face_incident_id
        )

        head_event = None
        if not self._calibrating and self.head_pose_baseline is not None:
            (
                head_event,
                self.head_deviation_start_time,
                self.head_flagged,
                self.head_incident_id
            ) = check_head_movement(
                landmarks,
                self.head_pose_baseline,
                frame_width,
                frame_height,
                self.head_deviation_start_time,
                self.head_flagged,
                self.head_incident_id
            )

        events = []
        for e in (absence_event, multi_event, head_event):
            if e:
                events.append(e)
                self.event_history.append(e)

        return {
            "face_count": num_faces,
            "faces": faces,
            "events": events,
            "calibrating": self._calibrating,
            "calibration_done": calibration_done_this_frame,
            "baseline_ready": self.head_pose_baseline is not None
        }

    def get_event_history(self):
        return self.event_history