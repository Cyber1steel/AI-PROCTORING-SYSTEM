# Team 2 — Philip Abbah: Recording & Media Capture

## A. What Was Implemented

This update adds the browser-side recording foundation for the student exam page.

The system now:

* Initializes a single `MediaStream` containing both video and audio tracks.
* Records that combined stream through a single `MediaRecorder`.
* Generates WebM recording chunks incrementally.
* Attaches elapsed-time metadata to each chunk.
* Maintains a bounded in-memory rolling buffer containing approximately the most recent 10 seconds of recording data.
* Exposes the recorded chunks to the Incident & Clip Engine for pre-event and event-window clip creation.

The implementation is designed to work with the existing exam camera/proctoring lifecycle without replacing the existing monitoring architecture.

## B. Files Changed

### `static/js/exam-recording.js`

Contains the browser recording implementation, including:

* `ExamRecordingManager`
* MIME/codec detection
* Combined audio/video `MediaStream` validation
* `MediaRecorder` setup
* Recording chunk collection
* Chunk timing metadata
* 10-second rolling buffer
* Chunk retrieval methods

### `templates/index.html`

Integrates the recording manager into the existing exam camera setup and monitoring lifecycle.

The existing camera/proctoring flow remains in place while the same media stream is also passed to the recording manager.

### `docs/team2-philip-recording.md`

Documents the recording architecture, public interface, timing strategy, responsibilities, limitations, and handoff to the next Team 2 engineer.

## C. APIs and Browser Technologies Used

* `navigator.mediaDevices.getUserMedia()`
* `MediaStream`
* `MediaRecorder`
* `MediaRecorder.isTypeSupported()`
* `performance.now()`
* `Blob`

## D. Recording Architecture

```text
Camera + Microphone
        ↓
    MediaStream
        ↓
   MediaRecorder
        ↓
   WebM Chunks
        ↓
 Timing Metadata
        ↓
 Rolling Buffer (~10 seconds)
        ↓
Incident & Clip Engine
```

The architecture uses **one combined `MediaStream` and one `MediaRecorder`** for both audio and video.

No separate audio recorder or video recorder is created.

## E. Recording Manager and Integration Contract

The recording implementation is located in:

`static/js/exam-recording.js`

The main class is:

`ExamRecordingManager`

The class is exposed to the exam page as:

```javascript
window.ExamRecordingManager
```

The actual recording manager instance is created in:

`templates/index.html`

using:

```javascript
const recordingManager = new window.ExamRecordingManager(...);
```

The Incident & Clip Engine should consume the existing `recordingManager` instance rather than creating another `MediaRecorder`, `MediaStream`, or recording manager.

### Public retrieval methods

The methods intended for the Incident & Clip Engine are:

```javascript
recordingManager.getRecentChunks(windowMs)
```

Retrieves chunks covering the requested recent time window.

```javascript
recordingManager.getChunksForWindow(startElapsedMs, endElapsedMs)
```

Retrieves chunks whose recorded time overlaps the requested elapsed-time window.

These methods provide the handoff between Philip's Recording & Media Capture role and Anosi's Incident & Clip Engine role.

## F. Chunk Data Structure

Each recorded chunk follows this structure:

```javascript
{
    blob: Blob,
    startElapsedMs: number,
    endElapsedMs: number,
    mimeType: string
}
```

The `blob` contains the recorded WebM media data.

The elapsed-time fields allow the Incident & Clip Engine to determine which chunks belong to the required pre-event and post-event windows.

## G. Rolling Buffer Behavior

* Target retention window: approximately 10 seconds.
* New recording chunks are added as they become available.
* Each chunk contains elapsed-time metadata.
* Chunks outside the configured retention window are discarded.
* The buffer remains bounded in memory and does not grow indefinitely.
* The Incident & Clip Engine can retrieve the required portion of the buffer through the public retrieval methods.

The rolling buffer is intended to provide the **pre-event recording window** needed when a violation occurs.

Incident detection, clip assembly, and upload are handled by other Team 2 roles.

## H. Timing Strategy

The recording manager establishes a `performance.now()` origin when recording starts.

Each recording chunk receives elapsed-time metadata relative to that recording origin:

```text
recording start
      ↓
performance.now() origin
      ↓
chunk elapsed timing
      ↓
rolling buffer
```

The implementation does not assume that the requested `MediaRecorder` `timeslice` represents an exact recording duration.

Instead, the actual browser timing associated with each `dataavailable` event is used when creating the chunk's elapsed-time metadata.

This allows downstream incident logic to work with the actual recording timeline rather than relying on theoretical fixed chunk durations.

## I. MIME Type and Codec Strategy

The recording manager checks browser support using `MediaRecorder.isTypeSupported()`.

The preferred configurations are checked in this order:

1. `video/webm;codecs=vp9,opus`
2. `video/webm;codecs=vp8,opus`
3. `video/webm`

This avoids assuming that a particular codec configuration is supported by every browser.

The resulting recording remains a WebM audio/video recording where supported by the browser.

## J. Error Handling

The recording manager accounts for common capture and recording failures, including:

* Permission denied (`NotAllowedError`)
* Missing camera or microphone (`NotFoundError`)
* Device unavailable or unreadable (`NotReadableError`)
* Unsupported recording configuration
* `MediaRecorder` failure

Recording failures are reported through the existing status/error handling rather than intentionally crashing the exam page.

## K. Testing and Validation

The following implementation checks were performed:

* Verified the existing exam camera setup and lifecycle before integrating the recording manager.
* Confirmed the recording implementation uses the existing camera stream rather than creating a second camera stream.
* Confirmed a single `MediaRecorder` handles the combined audio/video stream.
* Verified the rolling-buffer and chunk-retrieval logic in the implementation.
* Ran a JavaScript syntax check on the recording module with Node.

Live browser validation is still required for:

* Camera permission handling
* Microphone permission handling
* Actual audio/video capture
* Browser-specific `MediaRecorder` codec support
* Real recording playback

## L. Role Boundaries

This implementation is limited to **Recording & Media Capture**.

### Included in Philip's role

* Camera and microphone capture
* Combined `MediaStream`
* Single `MediaRecorder`
* WebM chunk generation
* Chunk timing metadata
* Approximately 10-second rolling buffer
* Public chunk-retrieval interface for the Incident & Clip Engine

### Not included in Philip's role

* AI violation detection
* Facial recognition or liveness detection
* Incident detection logic
* Incident state machine
* Incident clip assembly/finalization
* Backend upload
* Persistent clip storage
* Database violation storage
* Admin playback
* Admin dashboard changes

These responsibilities belong to the other Team 2 engineers.

## M. Handoff to the Incident & Clip Engine

When a violation occurs, the Incident & Clip Engine should use the existing recording manager to retrieve the required recording window.

The intended flow is:

```text
Existing violation event
        ↓
Incident & Clip Engine
        ↓
recordingManager.getRecentChunks(...)
        ↓
Pre-event recording data
        +
Post-event recording data
        ↓
Incident clip assembly
        ↓
Finalized clip + timing metadata
        ↓
Upload & Storage Engineer
```

The Recording & Media Capture layer does **not** assemble or upload incident clips.

Its responsibility ends at maintaining and exposing the rolling recording data required by the Incident & Clip Engine.
