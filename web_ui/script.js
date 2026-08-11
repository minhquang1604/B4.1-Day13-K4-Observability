const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatMessages = document.getElementById('chat-messages');
const statusIndicator = document.getElementById('status-indicator');
const dashboardFrame = document.getElementById('dashboard-frame');
const refreshDashboardBtn = document.getElementById('refresh-dashboard');

const USER_ID = 'u_demo_user';
const SESSION_ID = `s_${Math.random().toString(36).substring(2, 9)}`;

// Initialize
async function init() {
  await pollHealth();
  setInterval(pollHealth, 5000); // Poll status every 5s
}

// Health & Status
async function pollHealth() {
  try {
    const res = await fetch('/health');
    const data = await res.json();
    
    // Update Toggles based on active incidents
    const activeIncidents = data.incidents || [];
    ['rag_slow', 'llm_error', 'pii_leak'].forEach(id => {
      const toggle = document.getElementById(`toggle-${id}`);
      if (toggle) {
        toggle.checked = activeIncidents.includes(id);
      }
    });

    // Update Overall Status
    if (activeIncidents.length > 0) {
      statusIndicator.className = 'status incident';
      statusIndicator.textContent = `${activeIncidents.length} Incident(s) Active`;
    } else {
      statusIndicator.className = 'status healthy';
      statusIndicator.textContent = 'System Healthy';
    }
  } catch (err) {
    console.error('Failed to fetch health status', err);
  }
}

// Incident Control
['rag_slow', 'llm_error', 'pii_leak'].forEach(id => {
  const toggle = document.getElementById(`toggle-${id}`);
  if (toggle) {
    toggle.addEventListener('change', async (e) => {
      const action = e.target.checked ? 'enable' : 'disable';
      try {
        await fetch(`/incidents/${id}/${action}`, { method: 'POST' });
        await pollHealth();
        // Give backend time to log, then refresh dashboard
        setTimeout(() => dashboardFrame.contentWindow.location.reload(), 1000);
      } catch (err) {
        console.error(`Failed to ${action} ${id}`, err);
        e.target.checked = !e.target.checked; // revert
      }
    });
  }
});

// Chat Logic
chatForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = chatInput.value.trim();
  if (!text) return;

  chatInput.value = '';
  appendMessage('user', text);

  // loading state
  const loadingId = 'msg-' + Date.now();
  appendMessage('assistant', '...', null, loadingId);

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: USER_ID,
        session_id: SESSION_ID,
        feature: 'qa',
        message: text
      })
    });

    if (res.ok) {
        const data = await res.json();
        removeMessage(loadingId);
        appendMessage('assistant', data.answer, {
            latency: data.latency_ms,
            cost: data.cost_usd,
            tokens: (data.tokens_in || 0) + (data.tokens_out || 0)
        });
        setTimeout(() => dashboardFrame.contentWindow.location.reload(), 1500); 
    } else {
        removeMessage(loadingId);
        const err = await res.json();
        appendMessage('system', `Error: ${err.detail || 'Request Failed'}`);
        setTimeout(() => dashboardFrame.contentWindow.location.reload(), 1000);
    }
  } catch (err) {
    removeMessage(loadingId);
    appendMessage('system', 'Connection failed.');
  }
});

function appendMessage(role, text, metrics = null, id = null) {
  const msgDiv = document.createElement('div');
  msgDiv.className = `message ${role}`;
  if (id) msgDiv.id = id;

  let contentHtml = `<div class="bubble">${escapeHtml(text)}</div>`;
  
  if (metrics) {
    const isHighLatency = metrics.latency > 1500;
    contentHtml += `
      <div class="metrics-row">
        <span class="metric-pill ${isHighLatency ? 'high-latency' : ''}">
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
          ${metrics.latency}ms
        </span>
        <span class="metric-pill">
           <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>
          ${metrics.tokens} Tok
        </span>
        <span class="metric-pill">
          $${(metrics.cost || 0).toFixed(5)}
        </span>
      </div>`;
  }

  msgDiv.innerHTML = contentHtml;
  chatMessages.appendChild(msgDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeMessage(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function escapeHtml(unsafe) {
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

refreshDashboardBtn.addEventListener('click', () => {
    dashboardFrame.contentWindow.location.reload();
});

init();
