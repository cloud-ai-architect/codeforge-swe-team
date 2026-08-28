/**
 * CodeForge Task Dashboard
 * Polls API for recent tasks, displays status grid
 */

(function () {
  'use strict';

  const config = {
    apiUrl: window.CODEFORGE_API_URL || 'https://api.example.com',
    refreshIntervalMs: 5000,
  };

  const $ = (id) => document.getElementById(id);

  async function fetchTasks() {
    try {
      const response = await fetch(`${config.apiUrl}/v1/tasks?limit=20`);
      if (!response.ok) return [];
      return await response.json();
    } catch (err) {
      console.warn('Failed to fetch tasks:', err);
      return [];
    }
  }

  function statusClass(s) {
    if (['completed', 'done'].includes(s)) return 'completed';
    if (['failed', 'error'].includes(s)) return 'failed';
    if (['pending', 'planning', 'coding', 'testing', 'reviewing', 'pr_open', 'ci_running'].includes(s)) return 'running';
    return 'pending';
  }

  function renderTasks(tasks) {
    const container = $('tasks');
    if (!tasks.length) {
      container.innerHTML = '<p class="empty">No tasks yet. Create an issue to get started.</p>';
      return;
    }
    container.innerHTML = tasks.map((t) => `
      <article class="task">
        <div class="task-header">
          <span class="task-title">${escapeHtml(t.title || 'Untitled')}</span>
          <span class="task-status ${statusClass(t.status)}">${t.status || 'pending'}</span>
        </div>
        <div class="task-meta">
          <span>${t.repo || ''} #${t.issue_number || '?'}</span>
          ${t.pr_url ? ` · <a class="task-link" href="${escapeHtml(t.pr_url)}" target="_blank">View PR</a>` : ''}
          ${t.duration_seconds ? ` · ${t.duration_seconds}s` : ''}
        </div>
      </article>
    `).join('');
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  async function tick() {
    const tasks = await fetchTasks();
    renderTasks(tasks);
    const total = tasks.length;
    const running = tasks.filter((t) => statusClass(t.status) === 'running').length;
    const succeeded = tasks.filter((t) => t.status === 'completed').length;
    const failed = tasks.filter((t) => t.status === 'failed').length;
    $('stat-total').textContent = total;
    $('stat-running').textContent = running;
    $('stat-succeeded').textContent = succeeded;
    $('stat-failed').textContent = failed;
  }

  setInterval(tick, config.refreshIntervalMs);
  tick();
})();
