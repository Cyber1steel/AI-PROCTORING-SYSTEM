(function () {
    class RollingChunkBuffer {
        constructor(windowMs = 10000) {
            this.windowMs = windowMs;
            this.chunks = [];
        }

        addChunk(chunk) {
            if (!chunk || !chunk.blob || typeof chunk.startElapsedMs !== 'number' || typeof chunk.endElapsedMs !== 'number') {
                return false;
            }

            this.chunks.push(chunk);

            const newestElapsed = this.getNewestElapsedMs();
            const cutoff = newestElapsed - this.windowMs;
            this.chunks = this.chunks.filter((entry) => entry.endElapsedMs >= cutoff);

            return true;
        }

        getNewestElapsedMs() {
            if (!this.chunks.length) {
                return 0;
            }
            return this.chunks[this.chunks.length - 1].endElapsedMs;
        }

        getChunksForWindow(startElapsedMs, endElapsedMs) {
            return this.chunks.filter((chunk) => {
                const overlapsWindow = chunk.endElapsedMs >= startElapsedMs && chunk.startElapsedMs <= endElapsedMs;
                return overlapsWindow;
            });
        }

        getRecentChunks(windowMs = this.windowMs) {
            const newestElapsed = this.getNewestElapsedMs();
            if (!newestElapsed) {
                return [];
            }
            return this.getChunksForWindow(Math.max(0, newestElapsed - windowMs), newestElapsed);
        }

        clear() {
            this.chunks = [];
        }
    }

    class ExamRecordingManager {
        constructor(options = {}) {
            this.windowMs = options.windowMs || 10000;
            this.timesliceMs = options.timesliceMs || 1000;
            this.onError = options.onError || console.error;
            this.stream = null;
            this.recorder = null;
            this.state = 'idle';
            this.recordingStartTs = 0;
            this.lastChunkEndElapsedMs = 0;
            this.buffer = new RollingChunkBuffer(this.windowMs);
            this.mimeType = '';
        }

        getSupportedMimeType() {
            if (typeof MediaRecorder === 'undefined') {
                return '';
            }

            const candidates = [
                'video/webm;codecs=vp9,opus',
                'video/webm;codecs=vp8,opus',
                'video/webm'
            ];

            for (const candidate of candidates) {
                if (MediaRecorder.isTypeSupported(candidate)) {
                    return candidate;
                }
            }

            return '';
        }

        initializeFromStream(stream) {
            if (!stream) {
                throw new Error('Missing MediaStream for recording.');
            }

            const hasVideo = stream.getVideoTracks().length > 0;
            const hasAudio = stream.getAudioTracks().length > 0;
            if (!hasVideo || !hasAudio) {
                throw new Error('MediaStream must contain both video and audio tracks.');
            }

            if (!('MediaRecorder' in window)) {
                throw new Error('MediaRecorder is not supported in this browser.');
            }

            if (this.recorder && this.recorder.state !== 'inactive') {
                return this.recorder;
            }

            this.stream = stream;
            this.buffer.clear();
            this.state = 'idle';
            this.recordingStartTs = 0;
            this.lastChunkEndElapsedMs = 0;
            this.mimeType = this.getSupportedMimeType();

            const recorderOptions = this.mimeType ? { mimeType: this.mimeType } : undefined;
            this.recorder = new MediaRecorder(stream, recorderOptions);

            this.recorder.ondataavailable = (event) => {
                if (!event.data || event.data.size === 0) {
                    return;
                }

                if (!this.recordingStartTs) {
                    this.recordingStartTs = performance.now();
                }

                const now = performance.now();
                const elapsedMs = now - this.recordingStartTs;
                const chunkStartMs = Math.max(this.lastChunkEndElapsedMs, elapsedMs - this.timesliceMs);
                const chunkEndMs = elapsedMs;

                this.lastChunkEndElapsedMs = chunkEndMs;

                const chunk = {
                    blob: event.data,
                    startElapsedMs: chunkStartMs,
                    endElapsedMs: chunkEndMs,
                    mimeType: this.recorder.mimeType || event.data.type || 'video/webm'
                };

                this.buffer.addChunk(chunk);
            };

            this.recorder.onerror = (event) => {
                const detail = event && event.error ? event.error : new Error('MediaRecorder failed.');
                this.state = 'error';
                this.onError('Recorder error', detail);
            };

            this.recorder.onstop = () => {
                this.state = 'stopped';
                this.recordingStartTs = 0;
                this.lastChunkEndElapsedMs = 0;
            };

            stream.getTracks().forEach((track) => {
                track.addEventListener('ended', () => {
                    if (this.state === 'recording') {
                        this.stop();
                    }
                });
            });

            return this.recorder;
        }

        start() {
            if (!this.stream) {
                throw new Error('No MediaStream has been initialized for recording.');
            }

            if (!this.recorder) {
                this.initializeFromStream(this.stream);
            }

            if (this.state === 'recording') {
                return false;
            }

            try {
                this.state = 'starting';
                this.recordingStartTs = performance.now();
                this.lastChunkEndElapsedMs = 0;
                this.buffer.clear();
                this.recorder.start(this.timesliceMs);
                this.state = 'recording';
                return true;
            } catch (error) {
                this.state = 'error';
                this.onError('Unable to start recorder', error);
                return false;
            }
        }

        stop() {
            if (!this.recorder) {
                this.state = 'stopped';
                return;
            }

            try {
                if (this.recorder.state !== 'inactive') {
                    this.recorder.stop();
                }
            } catch (error) {
                this.onError('Failed to stop recorder cleanly', error);
            }

            this.releaseTracks();
            this.buffer.clear();
            this.state = 'stopped';
        }

        releaseTracks() {
            if (this.stream) {
                this.stream.getTracks().forEach((track) => track.stop());
            }
            this.stream = null;
            this.recorder = null;
            this.recordingStartTs = 0;
            this.lastChunkEndElapsedMs = 0;
        }

        addChunk(chunk) {
            return this.buffer.addChunk(chunk);
        }

        getChunksForWindow(startElapsedMs, endElapsedMs) {
            return this.buffer.getChunksForWindow(startElapsedMs, endElapsedMs);
        }

        getCurrentElapsedMs() {
            if (!this.recordingStartTs) {
                return this.lastChunkEndElapsedMs || 0;
            }

            return Math.max(this.lastChunkEndElapsedMs, performance.now() - this.recordingStartTs);
        }

        getRecentChunks(windowMs = this.windowMs) {
            return this.buffer.getRecentChunks(windowMs);
        }

        clear() {
            this.buffer.clear();
        }

        isRecording() {
            return this.state === 'recording';
        }
    }

    window.ExamRecordingManager = ExamRecordingManager;
})();
