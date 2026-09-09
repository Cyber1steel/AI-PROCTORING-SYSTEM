import time
import uuid


def check_absence(
    num_faces,
    absence_start_time,
    next_report_time,
    incident_id,
    threshold_seconds=3.5,
    report_interval=10
):
    event = None

    if num_faces == 0:

        if absence_start_time is None:
            absence_start_time = time.time()
            incident_id = f"ABS-{uuid.uuid4().hex[:6].upper()}"
            next_report_time = None

        elapsed = time.time() - absence_start_time

        if elapsed >= threshold_seconds and next_report_time is None:
            event = {
                "incident_id": incident_id,
                "event_type": "absence",
                "timestamp": time.strftime("%H:%M:%S"),
                "duration": round(elapsed, 1)
            }
            next_report_time = absence_start_time + report_interval

        elif next_report_time is not None and time.time() >= next_report_time:
            event = {
                "incident_id": incident_id,
                "event_type": "absence",
                "timestamp": time.strftime("%H:%M:%S"),
                "duration": round(elapsed, 1)
            }
            next_report_time += report_interval

    else:
        # Student returned — just reset state, nothing to log
        absence_start_time = None
        next_report_time = None
        incident_id = None

    return (
        event,
        absence_start_time,
        next_report_time,
        incident_id
    )