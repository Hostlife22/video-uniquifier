/** Node >=22 HTTP bridge. Import from a NestJS BullMQ WorkerHost processor.
 * job.data: { sourcePath, presetId?, packaging? }. Only trusted queue jobs may
 * contain sourcePath; never accept a public request's arbitrary local path.
 */
import { openAsBlob } from 'node:fs';
import { basename } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

export async function processReelsJob(job, {
  baseUrl = 'http://127.0.0.1:8765',
  token = process.env.VIDEO_REELS_API_TOKEN,
  isCancelled = async () => false,
  pollMs = 1000,
  timeoutMs = 4 * 60 * 60 * 1000,
  fetchImpl = fetch,
  openBlob = openAsBlob,
} = {}) {
  const base = new URL(baseUrl);
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  async function request(path, options = {}) {
    const response = await fetchImpl(new URL(path, base), {
      ...options, headers, signal: AbortSignal.timeout(120_000),
    });
    if (!response.ok) {
      const error = new Error(`Reels worker HTTP ${response.status}: ${await response.text()}`);
      error.code = 'worker_http';
      throw error;
    }
    return response.json();
  }
  if (await isCancelled(job)) throw Object.assign(new Error('Task cancelled'), { code: 'cancelled' });
  const form = new FormData();
  form.append('file', await openBlob(job.data.sourcePath), basename(job.data.sourcePath));
  form.append('preset_id', job.data.presetId ?? 'facebook_reels_drama_v1');
  if (job.data.packaging) form.append('packaging', JSON.stringify(job.data.packaging));
  const submitted = await request('/api/video-jobs', { method: 'POST', body: form });
  const path = `/api/video-jobs/${encodeURIComponent(submitted.job_id)}`;
  const started = Date.now();
  try {
    // Persist the Python attempt id in BullMQ's progress for operational tracing.
    for (;;) {
      if (await isCancelled(job)) {
        throw Object.assign(new Error('Task cancelled'), { code: 'cancelled' });
      }
      if (Date.now() - started > timeoutMs) {
        throw Object.assign(new Error('Reels worker timed out'), { code: 'worker_timeout' });
      }
      const status = await request(path);
      await job.updateProgress({ workerJobId: submitted.job_id, status: status.status,
                                 percent: Math.round(status.progress * 100) });
      if (status.status === 'success') {
        if (!status.output_url) throw new Error('Worker success omitted the output artifact');
        return { workerJobId: submitted.job_id, outputUrl: new URL(status.output_url, base).href,
                 reportUrl: new URL(status.report_url, base).href };
      }
      if (status.status === 'failed' || status.status === 'cancelled') {
        const error = new Error(status.error?.message ?? `Worker ${status.status}`);
        error.code = status.error?.code ?? status.status;
        error.workerJobId = submitted.job_id;
        throw error;
      }
      await delay(pollMs);
    }
  } catch (error) {
    // Includes network/polling failures: do not leave an unobserved encode running.
    try { await request(`${path}/cancel`, { method: 'POST' }); } catch { /* retain first error */ }
    throw error;
  }
}
