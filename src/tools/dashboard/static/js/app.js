document.addEventListener('DOMContentLoaded', () => {
    const tr = (key, params = {}) => window.i18n ? window.i18n.t(key, params) : key;
    // State
    const state = {
        games: [],
        videos: [],
        selectedVideos: new Set(),
        taskStatus: 'idle',
        errorIndex: 0,
        statusPollingInterval: null
    };

    // Stage configuration
    const STAGES = [
        { id: 'metadata', key: 'dashboard.metadata' },
        { id: 'frames', key: 'dashboard.frames' },
        { id: 'detection', key: 'dashboard.detection' },
        { id: 'clips', key: 'dashboard.clips' },
        { id: 'join', key: 'dashboard.join' },
        { id: 'audio', key: 'dashboard.audio' }
    ];

    // DOM Elements
    const elements = {
        gameSelect: document.getElementById('gameSelect'),
        dirInput: document.getElementById('dirInput'),
        scanBtn: document.getElementById('scanBtn'),
        videoList: document.getElementById('videoList'),
        selectAll: document.getElementById('selectAll'),
        fileCount: document.getElementById('fileCount'),
        selectedCount: document.getElementById('selectedCount'),
        startBtn: document.getElementById('startBtn'),
        cancelBtn: document.getElementById('cancelBtn'),
        taskStatusText: document.getElementById('taskStatusText'),
        globalStatus: document.getElementById('globalStatus'),
        statusDot: document.querySelector('.status-dot'),
        statusText: document.querySelector('.status-text'),
        // Progress elements
        currentVideoInfo: document.getElementById('currentVideoInfo'),
        stageList: document.getElementById('stageList'),
        detectionProgressFill: document.getElementById('detectionProgressFill'),
        detectionDetail: document.getElementById('detectionDetail'),
        killCount: document.getElementById('killCount'),
        clipCount: document.getElementById('clipCount'),
        outputSection: document.getElementById('outputSection'),
        outputList: document.getElementById('outputList'),
        // Error elements
        errorLog: document.getElementById('errorLog'),
        errorCount: document.getElementById('errorCount')
    };

    // --- Initialization ---
    init();

    function init() {
        fetchGames();
        setupEventListeners();
        checkTaskStatus();
        startStatusPolling();
        document.addEventListener('languageChanged', () => {
            setTaskStatus(state.taskStatus);
            elements.fileCount.textContent = tr('dashboard.fileCount', { count: state.videos.length });
        });
    }

    function setupEventListeners() {
        elements.scanBtn.addEventListener('click', scanDirectory);
        
        elements.selectAll.addEventListener('change', (e) => {
            const isChecked = e.target.checked;
            const checkboxes = elements.videoList.querySelectorAll('input[type="checkbox"]');
            
            checkboxes.forEach(cb => {
                cb.checked = isChecked;
                const path = cb.dataset.path;
                if (isChecked) {
                    state.selectedVideos.add(path);
                } else {
                    state.selectedVideos.delete(path);
                }
            });
            updateSelectionUI();
        });

        elements.startBtn.addEventListener('click', startTask);
        elements.cancelBtn.addEventListener('click', cancelTask);
    }

    // --- API Calls ---

    async function fetchGames() {
        try {
            const response = await fetch('/api/games');
            const data = await response.json();
            
            elements.gameSelect.innerHTML = '';
            
            if (data.games && data.games.length > 0) {
                data.games.forEach(game => {
                    const option = document.createElement('option');
                    option.value = game;
                    option.textContent = game;
                    elements.gameSelect.appendChild(option);
                });
            } else {
                const option = document.createElement('option');
                option.textContent = tr('dashboard.noGames');
                elements.gameSelect.appendChild(option);
            }
        } catch (error) {
            console.error('Failed to fetch games:', error);
            showToast(tr('dashboard.loadGamesFailed'), 'error');
        }
    }

    async function scanDirectory() {
        const directory = elements.dirInput.value.trim();
        if (!directory) {
            showToast(tr('dashboard.directoryRequired'), 'warning');
            return;
        }

        elements.scanBtn.disabled = true;
        elements.scanBtn.innerHTML = `<span class="icon">...</span> ${tr('dashboard.scanning')}`;

        try {
            const response = await fetch('/api/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ directory })
            });
            
            const data = await response.json();
            
            if (data.error) {
                showToast(data.error, 'error');
            } else {
                state.videos = data.videos || [];
                renderVideoList();
            }
            
        } catch (error) {
            console.error('Scan failed:', error);
            showToast(tr('dashboard.scanFailed'), 'error');
        } finally {
            elements.scanBtn.disabled = false;
            elements.scanBtn.innerHTML = `<span class="icon">Scan</span> ${tr('dashboard.scan')}`;
        }
    }

    async function startTask() {
        if (state.selectedVideos.size === 0) return;
        
        const game = elements.gameSelect.value;
        const videos = Array.from(state.selectedVideos);
        
        // Reset progress display
        resetProgressDisplay();
        setTaskStatus('running');
        state.errorIndex = 0;
        elements.errorLog.innerHTML = '';
        updateErrorCount(0);

        try {
            const response = await fetch('/api/task/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ game, videos })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast(tr('dashboard.taskStarted'), 'success');
            } else {
                setTaskStatus('failed');
                showToast(tr('dashboard.startFailed', { error: data.error || 'Unknown error' }), 'error');
            }
        } catch (error) {
            setTaskStatus('failed');
            showToast(tr('dashboard.startRequestFailed'), 'error');
        }
    }

    async function cancelTask() {
        if (!confirm(tr('dashboard.cancelConfirm'))) return;
        
        try {
            const response = await fetch('/api/task/cancel', { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                showToast(tr('dashboard.taskCancelled'), 'warning');
            }
        } catch (error) {
            showToast(tr('dashboard.cancelFailed'), 'error');
        }
    }

    async function checkTaskStatus() {
        try {
            const response = await fetch('/api/task/status');
            const data = await response.json();
            
            // Update status if changed
            if (state.taskStatus !== data.status) {
                setTaskStatus(data.status);
            }
            
            // Update progress display
            if (data.progress) {
                updateProgressDisplay(data.progress);
            }

            if (data.result) {
                updateResultDisplay(data.result);
            } else if (data.status === 'running' || data.status === 'idle') {
                clearOutputDisplay();
            }
            
            // Fetch errors if running
            if (data.status === 'running') {
                fetchErrors();
            }
            
        } catch (error) {
            console.warn('Status check failed:', error);
        }
    }

    async function fetchErrors() {
        try {
            const response = await fetch(`/api/task/errors?since=${state.errorIndex}`);
            const data = await response.json();
            
            if (data.errors && data.errors.length > 0) {
                data.errors.forEach(addErrorEntry);
                state.errorIndex = data.next_index;
            }
        } catch (error) {
            console.warn('Error fetch failed:', error);
        }
    }

    // --- UI Logic ---

    function renderVideoList() {
        elements.videoList.innerHTML = '';
        state.selectedVideos.clear();
        elements.selectAll.checked = false;
        
        if (state.videos.length === 0) {
            elements.videoList.innerHTML = `
                <div class="empty-state">
                    <span>${escapeHtml(tr('dashboard.noVideos'))}</span>
                </div>`;
            updateSelectionUI();
            return;
        }

        state.videos.forEach(video => {
            const item = document.createElement('div');
            item.className = 'video-item';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.dataset.path = video.path;
            checkbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    state.selectedVideos.add(video.path);
                } else {
                    state.selectedVideos.delete(video.path);
                }
                updateSelectionUI();
                elements.selectAll.checked = state.videos.length === state.selectedVideos.size;
            });

            const info = document.createElement('div');
            info.className = 'video-info';
            
            const name = document.createElement('div');
            name.className = 'video-name';
            name.textContent = video.name;
            name.title = video.path;
            
            const meta = document.createElement('div');
            meta.className = 'video-meta';
            meta.textContent = video.size_formatted;

            info.appendChild(name);
            info.appendChild(meta);
            
            item.appendChild(checkbox);
            item.appendChild(info);
            
            item.addEventListener('click', (e) => {
                if (e.target !== checkbox) {
                    checkbox.click();
                }
            });

            elements.videoList.appendChild(item);
        });

        elements.fileCount.textContent = tr('dashboard.fileCount', { count: state.videos.length });
        updateSelectionUI();
    }

    function updateSelectionUI() {
        const count = state.selectedVideos.size;
        elements.selectedCount.textContent = count;
        const isRunning = state.taskStatus === 'running';
        elements.startBtn.disabled = count === 0 || isRunning;
    }

    function setTaskStatus(status) {
        state.taskStatus = status;
        
        const isRunning = status === 'running';
        
        elements.startBtn.disabled = isRunning || state.selectedVideos.size === 0;
        
        if (isRunning) {
            elements.cancelBtn.classList.remove('hidden');
        } else {
            elements.cancelBtn.classList.add('hidden');
        }

        elements.gameSelect.disabled = isRunning;
        elements.dirInput.disabled = isRunning;
        elements.scanBtn.disabled = isRunning;
        const checkboxes = elements.videoList.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(cb => cb.disabled = isRunning);
        elements.selectAll.disabled = isRunning;

        const statusMap = {
            'idle': { text: tr('dashboard.idle'), color: '#94a3b8' },
            'running': { text: tr('dashboard.running'), color: '#00d9ff' },
            'completed': { text: tr('dashboard.completed'), color: '#4ade80' },
            'failed': { text: tr('dashboard.failed'), color: '#f87171' },
            'cancelled': { text: tr('dashboard.cancelled'), color: '#fbbf24' }
        };
        
        const info = statusMap[status] || statusMap['idle'];
        elements.taskStatusText.innerHTML = `${escapeHtml(tr('dashboard.status'))} <span style="color:${info.color}">${escapeHtml(info.text)}</span>`;
        
        elements.statusDot.style.backgroundColor = info.color;
        elements.statusDot.style.boxShadow = `0 0 8px ${info.color}`;
        elements.statusText.textContent = isRunning ? tr('dashboard.busy') : tr('dashboard.ready');
    }

    function resetProgressDisplay() {
        elements.currentVideoInfo.innerHTML = `<div class="video-label">${escapeHtml(tr('dashboard.preparing'))}</div>`;
        
        STAGES.forEach(stage => {
            const el = document.querySelector(`.stage-item[data-stage="${stage.id}"]`);
            if (el) {
                el.className = 'stage-item';
                el.querySelector('.stage-icon').textContent = '-';
            }
        });
        
        elements.detectionProgressFill.style.width = '0%';
        elements.detectionDetail.textContent = '';
        elements.killCount.textContent = '0';
        elements.clipCount.textContent = '0';
        clearOutputDisplay();
    }

    function updateProgressDisplay(progress) {
        // Update current video info
        if (progress.current_video) {
            let html = `<div class="video-label">${escapeHtml(progress.current_video)}</div>`;
            if (progress.total_videos > 1) {
                html += `<div class="video-counter">(${progress.current_video_index}/${progress.total_videos})</div>`;
            }
            elements.currentVideoInfo.innerHTML = html;
        }
        
        // Update stages
        const stages = progress.stages || {};
        STAGES.forEach(stage => {
            const el = document.querySelector(`.stage-item[data-stage="${stage.id}"]`);
            if (!el) return;
            
            const status = stages[stage.id] || 'pending';
            el.className = `stage-item ${status}`;
            
            let icon = '-';
            if (status === 'success') icon = 'OK';
            else if (status === 'running') icon = '...';
            else if (status === 'failed') icon = 'X';
            else if (status === 'skipped') icon = 'SKIP';
            
            el.querySelector('.stage-icon').textContent = icon;
        });
        
        // Update detection progress
        if (progress.detection_total > 0) {
            const percent = Math.min(100, Math.round((progress.detection_progress / progress.detection_total) * 100));
            elements.detectionProgressFill.style.width = `${percent}%`;
            elements.detectionDetail.textContent = `${progress.detection_progress}/${progress.detection_total}`;
        }
        
        // Update stats
        elements.killCount.textContent = progress.detected_kills || 0;
        elements.clipCount.textContent = progress.extracted_clips || 0;
    }

    function updateResultDisplay(result) {
        const outputFiles = Array.isArray(result.output_files) ? result.output_files : [];
        if (outputFiles.length === 0) {
            clearOutputDisplay();
            return;
        }

        elements.outputSection.classList.remove('hidden');
        elements.outputList.innerHTML = '';

        outputFiles.forEach(file => {
            const item = document.createElement('div');
            item.className = `output-item ${file.exists === false ? 'missing' : ''}`;

            const info = document.createElement('div');
            info.className = 'output-info';

            const title = document.createElement('div');
            title.className = 'output-name';
            title.textContent = file.label || file.name || tr('dashboard.generatedFile');

            const path = document.createElement('div');
            path.className = 'output-path';
            path.textContent = file.path || '';
            path.title = file.path || '';

            info.appendChild(title);
            info.appendChild(path);

            const actions = document.createElement('div');
            actions.className = 'output-actions';

            const copyBtn = document.createElement('button');
            copyBtn.className = 'btn btn-secondary btn-xs';
            copyBtn.textContent = tr('dashboard.copyPath');
            copyBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                copyOutputPath(file.path || '');
            });

            actions.appendChild(copyBtn);
            item.appendChild(info);
            item.appendChild(actions);
            elements.outputList.appendChild(item);
        });
    }

    function clearOutputDisplay() {
        if (!elements.outputSection || !elements.outputList) return;
        elements.outputSection.classList.add('hidden');
        elements.outputList.innerHTML = '';
    }

    function addErrorEntry(error) {
        const div = document.createElement('div');
        div.className = `error-entry ${error.level === 'WARNING' ? 'warning' : ''}`;
        div.innerHTML = `
            <span class="time">[${error.time || '??:??:??'}]</span>
            <span>${escapeHtml(error.message)}</span>
        `;
        elements.errorLog.appendChild(div);
        elements.errorLog.scrollTop = elements.errorLog.scrollHeight;
        
        updateErrorCount(elements.errorLog.children.length);
    }

    function updateErrorCount(count) {
        elements.errorCount.textContent = count;
        elements.errorCount.className = `error-count ${count === 0 ? 'zero' : ''}`;
    }

    // --- Polling ---

    function startStatusPolling() {
        if (state.statusPollingInterval) clearInterval(state.statusPollingInterval);
        state.statusPollingInterval = setInterval(checkTaskStatus, 1000);
    }

    // --- Utilities ---

    function showToast(message, type = 'info') {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    async function copyOutputPath(path) {
        if (!path) return;

        try {
            await navigator.clipboard.writeText(path);
            showToast(tr('dashboard.pathCopied'), 'success');
        } catch (error) {
            console.warn('Clipboard copy failed:', error);
            showToast(path, 'info');
        }
    }

    function escapeHtml(text) {
        if (!text) return '';
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});
