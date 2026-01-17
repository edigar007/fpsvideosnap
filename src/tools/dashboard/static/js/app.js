document.addEventListener('DOMContentLoaded', () => {
    // State
    const state = {
        games: [],
        videos: [],
        selectedVideos: new Set(),
        taskStatus: 'idle', // idle, running, completed, failed
        logIndex: 0,
        logPollingInterval: null,
        statusPollingInterval: null
    };

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
        logContainer: document.getElementById('logContainer'),
        clearLogsBtn: document.getElementById('clearLogsBtn'),
        taskStatusText: document.getElementById('taskStatusText'),
        globalStatus: document.getElementById('globalStatus'),
        statusDot: document.querySelector('.status-dot'),
        statusText: document.querySelector('.status-text')
    };

    // --- Initialization ---
    init();

    function init() {
        fetchGames();
        setupEventListeners();
        
        // Check if there's an existing task running
        checkTaskStatus();
        startStatusPolling();
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
        elements.clearLogsBtn.addEventListener('click', clearLogs);
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
                option.textContent = "未找到游戏配置";
                elements.gameSelect.appendChild(option);
            }
        } catch (error) {
            console.error('Failed to fetch games:', error);
            showToast('无法加载游戏列表', 'error');
        }
    }

    async function scanDirectory() {
        const directory = elements.dirInput.value.trim();
        if (!directory) {
            showToast('请输入视频目录', 'warning');
            return;
        }

        elements.scanBtn.disabled = true;
        elements.scanBtn.innerHTML = '<span class="icon">⏳</span> 扫描中...';

        try {
            const response = await fetch('/api/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ directory })
            });
            
            const data = await response.json();
            state.videos = data.videos || [];
            renderVideoList();
            
        } catch (error) {
            console.error('Scan failed:', error);
            showToast('扫描目录失败: ' + error.message, 'error');
        } finally {
            elements.scanBtn.disabled = false;
            elements.scanBtn.innerHTML = '<span class="icon">🔍</span> 扫描';
        }
    }

    async function startTask() {
        if (state.selectedVideos.size === 0) return;
        
        const game = elements.gameSelect.value;
        const videos = Array.from(state.selectedVideos);
        
        // Clear previous state
        clearLogs();
        setTaskStatus('running');

        try {
            const response = await fetch('/api/task/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    game: game,
                    videos: videos 
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast('任务已启动', 'success');
                startLogPolling();
            } else {
                setTaskStatus('failed');
                showToast('启动失败: ' + (data.error || '未知错误'), 'error');
            }
        } catch (error) {
            setTaskStatus('failed');
            showToast('启动请求失败', 'error');
        }
    }

    async function cancelTask() {
        if (!confirm('确定要取消当前任务吗？')) return;
        
        try {
            const response = await fetch('/api/task/cancel', { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                addLogEntry({ level: 'WARNING', message: '用户请求取消任务...', time: new Date().toLocaleTimeString() });
            }
        } catch (error) {
            showToast('取消请求失败', 'error');
        }
    }

    async function checkTaskStatus() {
        try {
            const response = await fetch('/api/task/status');
            const data = await response.json();
            
            // If status changed or initializing
            if (state.taskStatus !== data.status) {
                setTaskStatus(data.status);
                
                // If we just found a running task, start logging
                if (data.status === 'running' && !state.logPollingInterval) {
                    startLogPolling();
                }
            }
            
            if (data.status === 'completed' || data.status === 'failed') {
                stopLogPolling();
            }
            
        } catch (error) {
            console.warn('Status check failed:', error);
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
                    <span>未找到视频文件 (.mp4, .mkv, .avi)</span>
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
                
                // Update "Select All" state
                const allChecked = state.videos.length === state.selectedVideos.size;
                elements.selectAll.checked = allChecked;
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
            
            // Click on row toggles checkbox
            item.addEventListener('click', (e) => {
                if (e.target !== checkbox) {
                    checkbox.click();
                }
            });

            elements.videoList.appendChild(item);
        });

        elements.fileCount.textContent = `${state.videos.length} 个文件`;
        updateSelectionUI();
    }

    function updateSelectionUI() {
        const count = state.selectedVideos.size;
        elements.selectedCount.textContent = count;
        
        // Enable start button if at least one video is selected AND no task is running
        const isRunning = state.taskStatus === 'running';
        elements.startBtn.disabled = count === 0 || isRunning;
    }

    function setTaskStatus(status) {
        state.taskStatus = status;
        
        const isRunning = status === 'running';
        
        // Update Start Button
        elements.startBtn.disabled = isRunning || state.selectedVideos.size === 0;
        
        // Update Cancel Button
        if (isRunning) {
            elements.cancelBtn.classList.remove('hidden');
        } else {
            elements.cancelBtn.classList.add('hidden');
        }

        // Update Inputs
        elements.gameSelect.disabled = isRunning;
        elements.dirInput.disabled = isRunning;
        elements.scanBtn.disabled = isRunning;
        const checkboxes = elements.videoList.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(cb => cb.disabled = isRunning);
        elements.selectAll.disabled = isRunning;

        // Update Status Text
        const statusMap = {
            'idle': { text: '空闲', color: '#94a3b8' },
            'running': { text: '⏳ 处理中...', color: '#00d9ff' },
            'completed': { text: '✅ 已完成', color: '#4ade80' },
            'failed': { text: '❌ 失败', color: '#f87171' }
        };
        
        const info = statusMap[status] || statusMap['idle'];
        elements.taskStatusText.innerHTML = `状态: <span style="color:${info.color}">${info.text}</span>`;
        
        // Update Global Status Indicator
        elements.statusDot.style.backgroundColor = info.color;
        elements.statusDot.style.boxShadow = `0 0 8px ${info.color}`;
        elements.statusText.textContent = isRunning ? '系统忙碌' : '系统就绪';
    }

    // --- Logging System ---

    function startStatusPolling() {
        if (state.statusPollingInterval) clearInterval(state.statusPollingInterval);
        state.statusPollingInterval = setInterval(checkTaskStatus, 2000);
    }

    function startLogPolling() {
        if (state.logPollingInterval) clearInterval(state.logPollingInterval);
        
        // Initial poll immediately
        pollLogs();
        
        state.logPollingInterval = setInterval(pollLogs, 1000);
    }

    function stopLogPolling() {
        if (state.logPollingInterval) {
            clearInterval(state.logPollingInterval);
            state.logPollingInterval = null;
            // One final poll to get remaining logs
            pollLogs();
        }
    }

    async function pollLogs() {
        try {
            const response = await fetch(`/api/task/logs?poll=true&since=${state.logIndex}`);
            const data = await response.json();
            
            if (data.logs && data.logs.length > 0) {
                data.logs.forEach(addLogEntry);
                state.logIndex = data.next_index;
            }
            
            // If the server says task is done, ensure we stop polling eventually
            if (data.status !== 'running' && state.logPollingInterval) {
                // Let the status poller handle the final state switch
            }
            
        } catch (error) {
            console.error('Log poll failed:', error);
        }
    }

    function addLogEntry(log) {
        const div = document.createElement('div');
        
        // Map log level to CSS class
        let levelClass = 'log-info';
        if (log.level === 'ERROR' || log.level === 'CRITICAL') levelClass = 'log-error';
        else if (log.level === 'WARNING') levelClass = 'log-warning';
        else if (log.level === 'DEBUG') levelClass = 'log-debug';
        
        div.className = `log-entry ${levelClass}`;
        
        // Format: [14:30:05] [INFO] Message...
        div.innerHTML = `
            <span class="time">[${log.time || '??:??:??'}]</span>
            <span class="msg">${escapeHtml(log.message)}</span>
        `;
        
        elements.logContainer.appendChild(div);
        
        // Auto scroll to bottom
        elements.logContainer.scrollTop = elements.logContainer.scrollHeight;
    }

    function clearLogs() {
        elements.logContainer.innerHTML = '';
        state.logIndex = 0;
        addLogEntry({ level: 'INFO', message: '日志已清空', time: new Date().toLocaleTimeString() });
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
        
        // Remove after 3 seconds
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
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
