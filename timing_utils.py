def normalize_incident_timing_metadata(event_elapsed_ms=None, clip_start_elapsed_ms=None, clip_end_elapsed_ms=None):
    """Normalize incident timing values into the repository's elapsed recording timeline.

    The authoritative model remains the browser recording timeline created with
    performance.now() and carried forward through the rolling buffer, incident clip
    engine, and upload metadata.
    """

    def to_int(value):
        if value in (None, ''):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            raise ValueError(f"Invalid timing value: {value!r}")

    event_ms = to_int(event_elapsed_ms)
    clip_start_ms = to_int(clip_start_elapsed_ms)
    clip_end_ms = to_int(clip_end_elapsed_ms)

    if clip_start_ms is not None and clip_start_ms < 0:
        clip_start_ms = 0

    if event_ms is not None and clip_start_ms is not None and clip_start_ms > event_ms:
        raise ValueError("clip_start_elapsed_ms cannot be later than event_elapsed_ms")

    if event_ms is not None and clip_end_ms is not None and clip_end_ms < event_ms:
        raise ValueError("clip_end_elapsed_ms cannot be earlier than event_elapsed_ms")

    if clip_start_ms is not None and clip_end_ms is not None and clip_start_ms > clip_end_ms:
        raise ValueError("clip_start_elapsed_ms cannot be later than clip_end_elapsed_ms")

    video_offset_ms = None
    if event_ms is not None and clip_start_ms is not None:
        video_offset_ms = event_ms - clip_start_ms
        if video_offset_ms < 0:
            raise ValueError("video_offset_ms cannot be negative")

    return {
        "event_elapsed_ms": event_ms,
        "clip_start_elapsed_ms": clip_start_ms,
        "clip_end_elapsed_ms": clip_end_ms,
        "video_offset_ms": video_offset_ms,
    }
