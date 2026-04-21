document.addEventListener('DOMContentLoaded', () => {
    fetchProfile();
    fetchApplications();

    // Modal Handling
    window.showUploadModal = () => {
        document.getElementById('upload-modal').style.display = 'block';
    };

    window.closeModal = () => {
        document.getElementById('upload-modal').style.display = 'none';
    };

    // Form Handling
    const uploadForm = document.getElementById('upload-form');
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(uploadForm);
        const submitBtn = uploadForm.querySelector('button');
        
        try {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Analyzing...';
            
            const response = await fetch('/api/v1/resume/upload', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.detail || 'Analysis failed.');
            }
            
            alert(result.message);
            closeModal();
            fetchProfile(); // Refresh profile after upload
        } catch (error) {
            console.error('Upload failed:', error);
            alert(`Error: ${error.message}`);
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Start AI Analysis';
        }
    });
});

async function fetchProfile() {
    try {
        const response = await fetch('/api/v1/profile');
        const profile = await response.json();
        
        if (profile.error) return;

        document.getElementById('user-name').textContent = profile.name;
        document.getElementById('user-avatar').textContent = profile.name.charAt(0);

        // Update Skills
        const skillCloud = document.getElementById('skill-cloud');
        skillCloud.innerHTML = '';
        profile.skills.forEach(skill => {
            const span = document.createElement('span');
            span.className = 'skill-tag';
            span.textContent = skill;
            skillCloud.appendChild(span);
        });

        // Update Profile Details
        const profileData = document.getElementById('profile-data');
        profileData.innerHTML = `
            <p><strong>Headline:</strong> ${profile.headline}</p>
            <p><strong>Location:</strong> ${profile.location}</p>
            <p><strong>Experience:</strong> ${profile.experience.length} roles mapped</p>
        `;
    } catch (error) {
        console.error('Failed to fetch profile:', error);
    }
}

async function fetchApplications() {
    try {
        const response = await fetch('/api/v1/applications');
        const apps = await response.json();
        
        const appList = document.getElementById('app-list');
        appList.innerHTML = '';

        document.querySelector('#stat-applied .stat-value').textContent = apps.length;
        
        const highMatches = apps.filter(a => a.match_score > 0.7).length;
        document.querySelector('#stat-matches .stat-value').textContent = highMatches;

        apps.slice(0, 10).forEach(app => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${app.job_title}</td>
                <td>${app.company}</td>
                <td><span class="score-badge">${Math.round(app.match_score * 100)}%</span></td>
                <td><span class="status-badge status-${app.status}">${app.status}</span></td>
                <td><button class="btn btn-secondary btn-sm" onclick="viewJob('${app.job_id}')">Details</button></td>
            `;
            appList.appendChild(tr);
        });
    } catch (error) {
        console.error('Failed to fetch applications:', error);
    }
}

async function triggerSync() {
    const btn = event.target;
    const originalText = btn.textContent;
    
    try {
        btn.disabled = true;
        btn.textContent = 'Syncing...';
        const response = await fetch('/api/v1/pipeline/sync', { method: 'POST' });
        const result = await response.json();
        alert(result.message);
        fetchApplications();
    } catch (error) {
        console.error('Sync failed:', error);
        alert('Sync failed.');
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

function viewJob(id) {
    console.log('Viewing job:', id);
    // Placeholder for job detail view
}
