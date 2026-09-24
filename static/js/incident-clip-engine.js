(function () {
    const DEFAULT_PRE_EVENT_MS = 10000;
    const DEFAULT_POST_EVENT_MS = 5000;

    class IncidentClipEngine {
        constructor(options = {}) {
            this.recordingManager = options.recordingManager || null;
            this.preEventMs = options.preEventMs || DEFAULT_PRE_EVENT_MS;
            this.postEventMs = options.postEventMs || DEFAULT_POST_EVENT_MS;
            this.onIncidentReady = options.onIncidentReady || (() => { });
            this.onError = options.onError || console.error;

            this.state = 'IDLE';
            this.activeIncident = null;
            this.finalizationTimer = null;
            this.finalizedViolationIds = new Set();
        }

        getCurrentElapsedMs() {
            if (!this.recordingManager) {
                return 0;
            }

            if (typeof this.recordingManager.getCurrentElapsedMs === 'function') {
                return this.recordingManager.getCurrentElapsedMs();
            }

            if (typeof this.recordingManager.getRecentChunks !== 'function') {
                return 0;
            }

            const recentChunks = this.recordingManager.getRecentChunks(this.preEventMs + this.postEventMs);
            if (!recentChunks.length) {
                return 0;
            }

            return recentChunks[recentChunks.length - 1].endElapsedMs;
        }

        handleViolation(violation) {
            const violationId = violation && violation.id ? violation.id : violation;
            const eventType = violation && violation.event_type ? violation.event_type : 'UNKNOWN';

            if (!violationId) {
                return null;
            }

            if (this.finalizedViolationIds.has(violationId)) {
                return null;
            }

            const eventElapsedMs = (violation && typeof violation.eventElapsedMs === 'number')
                ? violation.eventElapsedMs
                : this.getCurrentElapsedMs();

            if (!this.activeIncident) {
                const clipStart = Math.max(0, eventElapsedMs - this.preEventMs);
                const clipEnd = eventElapsedMs + this.postEventMs;

                // Immediately preserve pre-event chunks so rolling buffer eviction
                // cannot drop required pre-event footage while we wait for post-event.
                let preservedPreChunks = [];
                try {
                    if (this.recordingManager && typeof this.recordingManager.getChunksForWindow === 'function') {
                        preservedPreChunks = this.recordingManager.getChunksForWindow(clipStart, eventElapsedMs) || [];
                    }
                } catch (err) {
                    this.onError('Failed to preserve pre-event chunks', err);
                    preservedPreChunks = [];
                }

                this.activeIncident = {
                    violationId,
                    eventType,
                    state: 'ACTIVE',
                    eventElapsedMs,
                    clipStartElapsedMs: clipStart,
                    clipEndElapsedMs: clipEnd,
                    createdAtMs: eventElapsedMs,
                    // preservedPreChunks holds references to chunk objects (blobs + timings)
                    preservedPreChunks
                };
                this.state = 'ACTIVE';
                this.scheduleFinalize();
                return this.activeIncident;
            }

            if (this.activeIncident.violationId === violationId) {
                return this.activeIncident;
            }

            const extendedEnd = eventElapsedMs + this.postEventMs;
            const newClipStart = Math.max(0, eventElapsedMs - this.preEventMs);

            // Update incident fields
            this.activeIncident.violationId = violationId;
            this.activeIncident.eventType = eventType;
            this.activeIncident.eventElapsedMs = eventElapsedMs;
            // If the new violation requires an earlier clip start, preserve earlier pre-chunks now
            if (newClipStart < (this.activeIncident.clipStartElapsedMs || 0)) {
                try {
                    if (this.recordingManager && typeof this.recordingManager.getChunksForWindow === 'function') {
                        const newPreserve = this.recordingManager.getChunksForWindow(newClipStart, eventElapsedMs) || [];
                        // merge newPreserve with existing preservedPreChunks, avoiding duplicates by timing
                        const existing = this.activeIncident.preservedPreChunks || [];
                        const merged = [];

                        // Add all chunks from newPreserve first (they are earlier)
                        newPreserve.forEach((c) => {
                            if (!merged.some((m) => m.startElapsedMs === c.startElapsedMs && m.endElapsedMs === c.endElapsedMs)) {
                                merged.push(c);
                            }
                        });

                        // Then add existing preserved chunks that are not duplicates
                        existing.forEach((c) => {
                            if (!merged.some((m) => m.startElapsedMs === c.startElapsedMs && m.endElapsedMs === c.endElapsedMs)) {
                                merged.push(c);
                            }
                        });

                        // Ensure sorted by startElapsedMs
                        merged.sort((a, b) => a.startElapsedMs - b.startElapsedMs);
                        this.activeIncident.preservedPreChunks = merged;
                    }
                } catch (err) {
                    this.onError('Failed to preserve extended pre-event chunks', err);
                }
            }

            this.activeIncident.clipStartElapsedMs = Math.min(this.activeIncident.clipStartElapsedMs || newClipStart, newClipStart);
            this.activeIncident.clipEndElapsedMs = Math.max(this.activeIncident.clipEndElapsedMs || 0, extendedEnd);
            this.activeIncident.createdAtMs = Math.min(this.activeIncident.createdAtMs || eventElapsedMs, eventElapsedMs);
            this.scheduleFinalize();
            return this.activeIncident;
        }

        scheduleFinalize() {
            if (this.finalizationTimer) {
                clearTimeout(this.finalizationTimer);
            }

            if (!this.activeIncident) {
                return;
            }

            const now = this.getCurrentElapsedMs();
            const delayMs = Math.max(0, (this.activeIncident.clipEndElapsedMs || now) - now + 25);

            this.finalizationTimer = setTimeout(() => {
                this.finalizeIncident();
            }, delayMs);
        }

        finalizeIncident() {
            if (!this.activeIncident || !this.recordingManager) {
                this.state = 'IDLE';
                this.activeIncident = null;
                return null;
            }

            const incident = this.activeIncident;
            const startElapsedMs = Math.max(0, incident.clipStartElapsedMs || 0);
            const endElapsedMs = incident.clipEndElapsedMs || this.getCurrentElapsedMs();

            // If we preserved pre-event chunks at violation time, use them and
            // only request the remaining post-event chunks now. This protects
            // against the rolling buffer evicting pre-event footage.
            const preserved = incident.preservedPreChunks || [];
            let postStart = startElapsedMs;
            if (preserved.length) {
                // preserved are expected ordered by startElapsedMs; determine end
                const preservedEnd = preserved[preserved.length - 1].endElapsedMs;
                postStart = Math.max(preservedEnd, startElapsedMs);
            }

            let postChunks = [];
            try {
                postChunks = this.recordingManager.getChunksForWindow(postStart, endElapsedMs) || [];
            } catch (err) {
                this.onError('Failed to retrieve post-event chunks', err);
                postChunks = [];
            }

            // Merge preserved + postChunks, avoiding duplicates by start/end timings
            const merged = [];
            const pushIfUnique = (c) => {
                if (!merged.some((m) => m.startElapsedMs === c.startElapsedMs && m.endElapsedMs === c.endElapsedMs)) {
                    merged.push(c);
                }
            };

            preserved.forEach(pushIfUnique);
            postChunks.forEach(pushIfUnique);

            // If merged is empty, there's no data to build the clip
            if (!merged.length) {
                this.state = 'IDLE';
                this.onError('No recording chunks were available to finalize the incident clip.', new Error('No chunks available'));
                this.activeIncident = null;
                return null;
            }

            // Ensure chronological order
            merged.sort((a, b) => a.startElapsedMs - b.startElapsedMs);

            const mimeType = merged[0].mimeType || 'video/webm';
            const blob = new Blob(merged.map((chunk) => chunk.blob), { type: mimeType });

            const finalizedIncident = {
                violationId: incident.violationId,
                eventType: incident.eventType,
                eventElapsedMs: incident.eventElapsedMs,
                clipStartElapsedMs: startElapsedMs,
                clipEndElapsedMs: endElapsedMs,
                blob,
                mimeType,
                createdAtMs: incident.createdAtMs
            };

            this.finalizedViolationIds.add(incident.violationId);
            this.state = 'READY';
            this.activeIncident = null;
            this.onIncidentReady(finalizedIncident);
            return finalizedIncident;
        }

        finalizeActiveIncidentImmediately() {
            if (this.finalizationTimer) {
                clearTimeout(this.finalizationTimer);
                this.finalizationTimer = null;
            }
            return this.finalizeIncident();
        }

        clear() {
            if (this.finalizationTimer) {
                clearTimeout(this.finalizationTimer);
                this.finalizationTimer = null;
            }
            this.activeIncident = null;
            this.state = 'IDLE';
        }
    }

    window.IncidentClipEngine = IncidentClipEngine;
})();
