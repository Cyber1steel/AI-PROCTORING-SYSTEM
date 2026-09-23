(function () {
    const DEFAULT_PRE_EVENT_MS = 10000;
    const DEFAULT_POST_EVENT_MS = 5000;

    class IncidentClipEngine {
        constructor(options = {}) {
            this.recordingManager = options.recordingManager || null;
            this.preEventMs = options.preEventMs || DEFAULT_PRE_EVENT_MS;
            this.postEventMs = options.postEventMs || DEFAULT_POST_EVENT_MS;
            this.onIncidentReady = options.onIncidentReady || (() => {});
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
                this.activeIncident = {
                    violationId,
                    eventType,
                    state: 'ACTIVE',
                    eventElapsedMs,
                    clipStartElapsedMs: Math.max(0, eventElapsedMs - this.preEventMs),
                    clipEndElapsedMs: eventElapsedMs + this.postEventMs,
                    createdAtMs: eventElapsedMs
                };
                this.state = 'ACTIVE';
                this.scheduleFinalize();
                return this.activeIncident;
            }

            if (this.activeIncident.violationId === violationId) {
                return this.activeIncident;
            }

            const extendedEnd = eventElapsedMs + this.postEventMs;
            this.activeIncident.violationId = violationId;
            this.activeIncident.eventType = eventType;
            this.activeIncident.eventElapsedMs = eventElapsedMs;
            this.activeIncident.clipStartElapsedMs = Math.max(0, eventElapsedMs - this.preEventMs);
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
            const incidentChunks = this.recordingManager.getChunksForWindow(startElapsedMs, endElapsedMs);

            if (!incidentChunks.length) {
                this.state = 'IDLE';
                this.onError('No recording chunks were available to finalize the incident clip.', new Error('No chunks available'));
                this.activeIncident = null;
                return null;
            }

            const mimeType = incidentChunks[0].mimeType || 'video/webm';
            const blob = new Blob(incidentChunks.map((chunk) => chunk.blob), { type: mimeType });

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
