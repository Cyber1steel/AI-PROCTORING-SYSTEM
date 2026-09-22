# Team 2 - Philip Abbah: Recording & Media Capture

## A. What was implemented

This update adds the browser-side recording foundation for the student exam page. The system now initializes a single `MediaStream` with both video and audio tracks, records it through a single `MediaRecorder`, and stores incrementally generated WebM chunks in a bounded in-memory rolling buffer. The buffer is designed to keep approximately the most recent 10 seconds of footage so the incident engine can fetch recent chunks before a violation.

## B. Files changed

- `static/js/exam-recording.js`
  - Added the recording manager, MIME detection, chunk timing metadata, and 10-second rolling buffer.
- `templates/index.html`
  - Integrated the recording manager into the existing exam camera setup and monitoring lifecycle without replacing the current proctoring page structure.

## C. APIs used

- `navigator.mediaDevices.getUserMedia()`
- `MediaStream`
- `MediaRecorder`
- `MediaRecorder.isTypeSupported()`
- `performance.now()`
- `Blob`

## D. Recording flow

`camera + microphone` → `MediaStream` → `MediaRecorder` → WebM chunks → timing metadata → rolling buffer

## E. Rolling buffer behavior

- Target retention window: approximately 10 seconds.
- Each chunk is added with actual elapsed timing metadata.
- Older chunks are discarded as soon as the newest chunk moves beyond the fixed window.
- The buffer is in-memory and bounded, so it does not grow indefinitely.
- Future incident logic can retrieve recent data through `getRecentChunks()` or `getChunksForWindow()`.

## F. Timing strategy

The recording manager establishes a `performance.now()` origin when the recorder starts. Each `dataavailable` event is tagged with the actual elapsed time at the moment the chunk arrives. This means chunk boundaries are based on real browser timing rather than a theoretical fixed `timeslice`. The system does not assume `timeslice === exact chunk duration`.

## G. MIME type strategy

The manager checks browser support in priority order:

1. `video/webm;codecs=vp9,opus`
2. `video/webm;codecs=vp8,opus`
3. `video/webm`

This prevents blind codec assumptions and keeps compatibility with different browsers.

## H. Integration contract

The recording manager exposes these behaviors for the incident engine:

- `addChunk(chunk)`
- `getChunksForWindow(startElapsedMs, endElapsedMs)`
- `getRecentChunks(windowMs)`
- `clear()`

The chunk contents follow the expected shape:

```js
{
  blob: Blob,
  startElapsedMs: number,
  endElapsedMs: number,
  mimeType: string
}
```

## I. Error handling

The manager accounts for the following scenarios:

- permission denied (`NotAllowedError`)
- no available camera or microphone (`NotFoundError`)
- unreadable device (`NotReadableError`)
- unsupported recording configuration
- recorder failure

Recording failures do not crash the exam page, but they are reported to the console and the status UI.

## J. Testing

The following checks were performed locally:

- Verified the repo contains the existing exam camera setup and lifecycle.
- Confirmed there was already a single stream and a simple `MediaRecorder` loop in the student page.
- Ran a syntax check on the new JavaScript module with Node.

The environment available here does not include a real browser automation session, so live camera, microphone, and browser playback validation still need a real-device browser test.

## K. Limitations

- Real browser permission flows and actual microphone/camera capture still need validation in a live browser session.
- The project still does not include the incident clip assembly or upload flow; that remains the responsibility of the next Team 2 engineer.
