/**
 * TACTICAL_OS_ORCHESTRATOR v2.0
 * High-Fidelity Interaction Logic for Command Console
 */

// -------------------------------------------------------------------------
// REFINED TELEMETRY LOGGING (Typewriter Effect)
// -------------------------------------------------------------------------
window.addAgentLog = (agent, message) => {
    const stream = document.getElementById('terminal-stream');
    if (!stream) return;

    const entry = document.createElement('div');
    entry.className = 'log-entry';
    const timestamp = new Date().toLocaleTimeString('en-GB', { hour12: false });
    const agentClass = `log-${agent}`;
    
    // Create the structured log entry
    entry.innerHTML = `<span class="log-timestamp">[${timestamp}]</span> <span class="${agentClass}">${agent.toUpperCase()}:</span> <span class="msg-content"></span>`;
    stream.appendChild(entry);
    
    // Typewriter simulation
    const content = entry.querySelector('.msg-content');
    let i = 0;
    const type = () => {
        if (i < message.length) {
            content.textContent += message.charAt(i);
            i++;
            setTimeout(type, 15);
        }
    };
    type();
    
    stream.scrollTop = stream.scrollHeight;
};

// -------------------------------------------------------------------------
// SESSION & PROFILE MANAGEMENT
// -------------------------------------------------------------------------
async function checkSession() {
    try {
        addAgentLog('orchestrator', 'INITIATING_SESSION_HANDSHAKE...');
        const resp = await fetch('/api/v1/profile');
        const profile = await resp.json();

        addAgentLog('orchestrator', 'AUTHORIZATION_VERIFIED. PROFILE_SYNC_COMPLETE.');
        updateUserUI(profile);
        return profile;
    } catch (err) {
        console.error('Session Error:', err);
        addAgentLog('orchestrator', 'NETWORK_SIGNAL_FAILURE. OPERATING_IN_DEGRADED_MODE.');
    }
}

function updateUserUI(profile) {
    if (!profile) return;
    const nameElem = document.getElementById('user-name');
    const avatarElem = document.getElementById('user-avatar');
    
    if (nameElem && profile.name) nameElem.textContent = profile.name.toUpperCase();
    if (avatarElem && profile.name) avatarElem.textContent = profile.name.charAt(0).toUpperCase();
}

// -------------------------------------------------------------------------
// DATA ORCHESTRATION
// -------------------------------------------------------------------------
window.fetchApplications = async () => {
    try {
        const response = await fetch('/api/v1/applications');
        const apps = await response.json();
        renderApplications(apps);
        updateFeaturedCard(apps[0]);
    } catch (err) {
        addAgentLog('orchestrator', 'ERROR: DATA_LOAD_FAILURE_APPLICATIONS');
    }
};

function renderApplications(apps) {
    const list = document.getElementById('app-list-full');
    const tray = document.getElementById('tray-list-data');
    if (!list && !tray) return;

    const sourceMap = { 'linkedin': 'LD', 'indeed': 'ID', 'glassdoor': 'GD', 'naukri': 'NK' };
    
    const rows = apps.map(app => `
        <tr>
            <td>${app.job_title}</td>
            <td><span style="color:var(--neon-cyan)">[${sourceMap[app.source]||'??'}]</span> ${app.company}</td>
            <td>${Math.round(app.match_score * 100)}%</td>
            <td><span style="color:var(--toxic-green)">[${app.status.toUpperCase()}]</span></td>
            <td>
                <button class="btn-tactical" onclick="tailorApplication('${app.source}', '${app.job_id}', this)">[ TAILOR ]</button>
            </td>
        </tr>
    `).join('');

    if (list) list.innerHTML = rows;
    if (tray) tray.innerHTML = rows;
}

function updateFeaturedCard(latest) {
    if (!latest) return;
    const title = document.getElementById('job-title-display');
    const company = document.getElementById('job-company-display');
    if (title) title.textContent = latest.job_title.toUpperCase();
    if (company) company.textContent = `TARGET_ORG: ${latest.company.toUpperCase()}`;
    
    const applyBtn = document.getElementById('apply-btn');
    if (applyBtn) {
        applyBtn.href = latest.job_url;
        applyBtn.onclick = () => updateStatus(latest.source, latest.job_id, 'Applied');
    }
}

// -------------------------------------------------------------------------
// TACTICAL ACTIONS
// -------------------------------------------------------------------------
window.triggerSync = async () => {
    addAgentLog('scout', 'INITIATING_MARKET_SCAN_SEQUENCE...');
    try {
        const response = await fetch('/api/v1/pipeline/run', { method: 'POST' });
        addAgentLog('scout', 'SCAN_COMPLETE. UPDATING_MISSION_TELEMETRY.');
        fetchApplications();
    } catch (err) {
        addAgentLog('orchestrator', 'SIGNAL_FAILURE: SCAN_INTERRUPTED');
    }
};

window.tailorApplication = async (source, jobId, btn) => {
    addAgentLog('analyst', `CALIBRATING_DNA_FOR_TARGET: ${jobId}...`);
    const orig = btn.textContent;
    btn.textContent = '[ CALIB... ]';
    try {
        await fetch(`/api/v1/applications/${source}/${jobId}/tailor`, { method: 'POST' });
        addAgentLog('analyst', 'CALIBRATION_SUCCESS. HANDING_OFF_TO_LIAISON.');
        fetchApplications();
    } catch (err) { addAgentLog('orchestrator', 'ERROR_IN_TAILORING'); }
    finally { btn.textContent = orig; }
};

window.updateStatus = async (source, jobId, status) => {
    try {
        await fetch(`/api/v1/applications/${source}/${jobId}/status`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({status})
        });
        fetchApplications();
    } catch (err) { addAgentLog('orchestrator', 'STATUS_SYNC_FAILURE'); }
};

// -------------------------------------------------------------------------
// SPA VIEW CONTROL
// -------------------------------------------------------------------------
window.switchView = (viewId) => {
    document.querySelectorAll('.spa-view').forEach(v => v.classList.remove('active'));
    document.getElementById(`view-${viewId}`)?.classList.add('active');
    
    document.querySelectorAll('.nav-links li').forEach(li => li.classList.remove('active'));
    document.querySelector(`.nav-links a[href="#${viewId}"]`)?.parentElement.classList.add('active');

    const labels = {
        'dashboard': 'COMMAND_CONSOLE: ACTIVE_MISSION',
        'applications': 'DATABASE_TARGETS: READ_ONLY',
        'profile': 'VITAL_COLLECTION: DNA_ID',
        'settings': 'ENGINEERING_CONFIG: ACCESS_GRANTED'
    };
    document.getElementById('view-title').textContent = labels[viewId] || 'CORE_MODULE';
};

// -------------------------------------------------------------------------
// BOOTSTRAP
// -------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    const profile = await checkSession();
    if (profile) {
        addAgentLog('orchestrator', 'BOOT_SEQUENCE_COMPLETE.');
        fetchApplications();

        document.querySelectorAll('.nav-links a').forEach(link => {
            link.addEventListener('click', (e) => {
                const id = link.getAttribute('href').substring(1);
                if (id) { e.preventDefault(); switchView(id); }
            });
        });
    }
});
