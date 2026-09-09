import time
import uuid


def check_multiple_faces(
    num_faces,
    start_time,
    flagged,
    incident_id,
    threshold_seconds=2
):
    event = None

    if num_faces > 1:

        if start_time is None:
            start_time = time.time()
            incident_id = f"MUL-{uuid.uuid4().hex[:6].upper()}"

        elapsed = time.time() - start_time

        if elapsed >= threshold_seconds and not flagged:
            event = {
                "incident_id": incident_id,
                "event_type": "multiple_faces",
                "timestamp": time.strftime("%H:%M:%S"),
                "duration": round(elapsed, 1),
                "num_faces": num_faces
            }
            flagged = True

    else:
        start_time = None
        flagged = False
        incident_id = None

    return event, start_time, flagged, incident_id

