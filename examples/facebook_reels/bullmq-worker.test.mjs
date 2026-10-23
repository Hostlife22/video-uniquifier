import assert from 'node:assert/strict';
import test from 'node:test';
import { processReelsJob } from './bullmq-worker.mjs';

function fixture(statuses, overrides = {}) {
  const requests = [];
  const progress = [];
  const job = { data: { sourcePath: '/trusted/drama.mp4' },
                updateProgress: async (value) => progress.push(value) };
  const options = { pollMs: 0, token: 'internal-token',
    openBlob: async () => new Blob(['video']),
    fetchImpl: async (url, init) => {
      requests.push({ path: url.pathname, ...init });
      assert.equal(init.headers.Authorization, 'Bearer internal-token');
      if (init.method === 'POST') return Response.json({ job_id: 'abc', status: 'queued' });
      return Response.json(statuses.shift());
    }, ...overrides };
  return { job, options, requests, progress };
}

test('uploads a file and only returns a completed artifact', async () => {
  const f = fixture([{ status: 'processing', progress: 0.3 },
    { status: 'success', progress: 1, output_url: '/api/result.mp4', report_url: '/api/report' }]);
  const result = await processReelsJob(f.job, f.options);
  assert.equal(result.outputUrl, 'http://127.0.0.1:8765/api/result.mp4');
  assert.deepEqual(f.progress.map((p) => p.percent), [30, 100]);
  assert.equal(f.requests[0].body.get('file').name, 'drama.mp4');
});

test('propagates processing errors so BullMQ can retry with a fresh attempt', async () => {
  const f = fixture([{ status: 'failed', progress: 0.4,
    error: { code: 'quality_failed', message: 'decode failed' } }]);
  await assert.rejects(processReelsJob(f.job, f.options), { code: 'quality_failed' });
  assert.equal(f.requests.at(-1).path, '/api/video-jobs/abc/cancel');
});

test('cancels the Python task when the application records a cancellation', async () => {
  let checks = 0;
  const f = fixture([], { isCancelled: async () => ++checks > 1 });
  await assert.rejects(processReelsJob(f.job, f.options), { code: 'cancelled' });
  assert.equal(f.requests.at(-1).path, '/api/video-jobs/abc/cancel');
});

test('rejects upload HTTP errors without inventing a completed job', async () => {
  const f = fixture([], { fetchImpl: async () => new Response('queue full', { status: 429 }) });
  await assert.rejects(processReelsJob(f.job, f.options), { code: 'worker_http' });
  assert.deepEqual(f.progress, []);
});
