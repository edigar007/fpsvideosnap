/**
 * Main application coordinator for Config Assistant v2.0
 */
document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const gameSelector = document.getElementById('game-selector');
    const addGameBtn = document.getElementById('add-game-btn');
    const addGameModal = document.getElementById('add-game-modal');
    const confirmAddGameBtn = document.getElementById('confirm-add-game');
    const newGameNameInput = document.getElementById('new-game-name');
    const closeModalBtns = document.querySelectorAll('.close-modal');
    
    const fileInput = document.getElementById('file-input');
    const uploadBtn = document.getElementById('upload-btn');
    const dropZone = document.getElementById('drop-zone');
    
    const statusMessage = document.getElementById('status-message');
    const loadingOverlay = document.getElementById('loading-overlay');
    const downloadConfigBtn = document.getElementById('download-config-btn');
    const testConfigBtn = document.getElementById('test-config-btn');
    const testPanel = document.getElementById('config-test-panel');
    const testResultSummary = document.getElementById('test-result-summary');
    const testResultBadge = document.getElementById('test-result-badge');
    const testResultDetails = document.getElementById('test-result-details');

    // App State
    const appState = {
        currentGame: '',
        currentRuleName: null,  // null = global, string = specific rule
        config: {
            game: '',
            detection: {
                killfeed_roi: null,
                ocr: { enabled: true, keywords: [], threshold: 0.8 },
                templates: {},
                colors: {}
            }
        },
        gamesList: [],
        currentImagePath: ''
    };

    /**
     * Initialize Application
     */
    async function init() {
        console.log('[App] Initializing v2.0...');
        await loadGamesList();
        setupEventListeners();
        
        // Load default config if available
        if (appState.gamesList.length > 0) {
            gameSelector.value = appState.gamesList[0];
            await loadGameConfig(appState.gamesList[0]);
        }
    }

    /**
     * Load list of configured games from backend
     */
    async function loadGamesList() {
        try {
            const response = await fetch('/api/game/list');
            const data = await response.json();
            appState.gamesList = data.games || [];
            
            // Populate dropdown
            gameSelector.innerHTML = appState.gamesList
                .map(g => `<option value="${g}">${g}</option>`)
                .join('');
                
            if (appState.gamesList.length === 0) {
                gameSelector.innerHTML = '<option value="">请新增游戏...</option>';
            }
        } catch (err) {
            console.error('Failed to load games list:', err);
            showStatus('加载游戏列表失败', 'error');
        }
    }

    /**
     * Load specific game configuration
     */
    async function loadGameConfig(gameId) {
        if (!gameId) return;
        
        showLoading(`正在加载 ${gameId} 的配置...`);
        try {
            const response = await fetch(`/api/config/${gameId}`);
            const config = await response.json();
            
            appState.currentGame = gameId;
            appState.config = config;
            resetTestResult('上传图片后点击测试配置');
            
            // Sync with other modules
            if (window.configPreview) {
                window.configPreview.update(config);
            }
            
            if (window.canvasState && config.detection && config.detection.killfeed_roi) {
                window.canvasState.roi = config.detection.killfeed_roi;
                window.canvasState.render();
                
                if (window.roiTab) {
                    window.roiTab.setROI(config.detection.killfeed_roi);
                }
            }

            if (window.ocrTab && config.detection && config.detection.ocr) {
                window.ocrTab.setConfig(config.detection.ocr);
            }

            if (window.templateTab && config.detection && config.detection.templates) {
                window.templateTab.setTemplates(config.detection.templates);
            }

            if (window.colorTab && config.detection && config.detection.colors) {
                window.colorTab.setColors(config.detection.colors);
            }

            if (window.rulesTab && config.detection && config.detection.rules) {
                window.rulesTab.setRules(config.detection.rules);
            }
            
            showStatus(`${gameId} 配置已加载`, 'success');
        } catch (err) {
            console.error('Failed to load config:', err);
            showStatus('加载配置失败', 'error');
        } finally {
            hideLoading();
        }
    }

    /**
     * Event Listeners Setup
     */
    function setupEventListeners() {
        // Game Selection
        gameSelector.addEventListener('change', (e) => loadGameConfig(e.target.value));
        
        // Add Game Modal
        addGameBtn.addEventListener('click', () => addGameModal.classList.add('active'));
        closeModalBtns.forEach(btn => btn.addEventListener('click', () => addGameModal.classList.remove('active')));
        
        confirmAddGameBtn.addEventListener('click', async () => {
            const name = newGameNameInput.value.trim();
            if (!name) return alert('请输入游戏名称');
            
            try {
                const response = await fetch('/api/game/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ game_name: name })
                });
                
                if (response.ok) {
                    await loadGamesList();
                    gameSelector.value = name;
                    await loadGameConfig(name);
                    addGameModal.classList.remove('active');
                    newGameNameInput.value = '';  // 清空输入框
                } else {
                    const errorData = await response.json();
                    alert(`创建失败: ${errorData.error || '未知错误'}`);
                }
            } catch (err) {
                console.error(err);
                alert('网络错误');
            }
        });

        // Image Upload
        uploadBtn.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', handleFileSelect);
        
        // Drag and Drop - 扩大拖拽区域到整个左侧面板
        const canvasPanel = document.querySelector('.canvas-panel');
        
        canvasPanel.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('dragover');
        });
        
        canvasPanel.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            // 只在真正离开面板时移除样式
            if (e.target === canvasPanel) {
                dropZone.classList.remove('dragover');
            }
        });
        
        canvasPanel.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                handleFile(e.dataTransfer.files[0]);
            }
        });
        
        // 保留原有的 dropZone 事件，以防万一
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                handleFile(e.dataTransfer.files[0]);
            }
        });

        // Export/Download
        downloadConfigBtn.addEventListener('click', () => {
            if (!appState.currentGame) return;
            window.location.href = `/api/config/${appState.currentGame}/export`;
        });

        if (testConfigBtn) {
            testConfigBtn.addEventListener('click', () => testCurrentConfig());
        }

        // Global Keyboard Shortcuts
        document.addEventListener('keydown', (e) => {
            // Avoid shortcuts when typing in inputs/textareas
            if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
                if (e.key === 'Escape') {
                    document.activeElement.blur();
                }
                return;
            }

            const key = e.key.toLowerCase();
            
            // Tab switching: 1-5
            if (['1', '2', '3', '4', '5'].includes(key)) {
                const tabs = ['roi', 'ocr', 'templates', 'colors', 'rules'];
                if (window.tabManager) {
                    window.tabManager.switchTab(tabs[parseInt(key) - 1]);
                }
            }
            
            // Save: S
            if (key === 's') {
                e.preventDefault();
                downloadConfigBtn.click();
            }
            
            // Exit/Cancel: Escape
            if (e.key === 'Escape') {
                if (addGameModal.classList.contains('active')) {
                    addGameModal.classList.remove('active');
                } else if (window.canvasState) {
                    window.canvasState.resetSelection();
                }
            }
        });
    }

    function handleFileSelect(e) {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    }

    async function handleFile(file) {
        if (!file.type.startsWith('image/')) {
            return showStatus('请上传图片文件', 'error');
        }

        showLoading('正在上传图片...');
        
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (data.error) throw new Error(data.error);
            
            // Store absolute path for backend tools (OCR, Template)
            appState.currentImagePath = data.path;
            resetTestResult('图片已加载，点击测试配置');
            
            // Preview locally
            const reader = new FileReader();
            reader.onload = (e) => {
                const img = new Image();
                img.onload = () => {
                    if (window.canvasState) {
                        window.canvasState.setImage(img);
                        dropZone.style.display = 'none';
                    }
                };
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);
            
            showStatus('图片加载成功', 'success');
        } catch (err) {
            console.error('Upload failed:', err);
            showStatus('图片上传失败', 'error');
        } finally {
            hideLoading();
        }
    }

    /**
     * UI Utils
     */
    function showStatus(msg, type = 'info') {
        statusMessage.textContent = msg;
        statusMessage.className = `status-badge ${type}`;
        setTimeout(() => {
            if (statusMessage.textContent === msg) {
                // If we are in rule mode, restore rule status, else 'Ready'
                if (appState.currentRuleName) {
                    updateRuleIndicator();
                } else {
                    statusMessage.textContent = '准备就绪';
                    statusMessage.className = 'status-badge';
                }
            }
        }, 3000);
    }

    function resetTestResult(summary = '上传图片后点击测试配置') {
        if (!testPanel) return;
        testPanel.className = 'config-test-panel idle';
        testResultBadge.textContent = '待测试';
        testResultSummary.textContent = summary;
        testResultDetails.innerHTML = '';
    }

    async function testCurrentConfig() {
        if (!appState.currentGame) {
            showStatus('请先选择游戏', 'error');
            return;
        }
        if (!appState.currentImagePath) {
            showStatus('请先上传图片', 'error');
            resetTestResult('请先上传要测试的图片');
            return;
        }

        showLoading('正在测试当前配置...');
        setTestRunning();

        try {
            const response = await fetch(`/api/config/${appState.currentGame}/test-image`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image_path: appState.currentImagePath })
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || '测试失败');
            }

            renderTestResult(data);
            showStatus(data.is_kill ? '测试成功：配置命中' : '测试失败：未命中', data.is_kill ? 'success' : 'error');
        } catch (err) {
            console.error('Config test failed:', err);
            renderTestError(err.message || '测试失败');
            showStatus('配置测试失败', 'error');
        } finally {
            hideLoading();
        }
    }

    function setTestRunning() {
        if (!testPanel) return;
        testPanel.className = 'config-test-panel running';
        testResultBadge.textContent = '测试中';
        testResultSummary.textContent = '正在按当前配置检测图片...';
        testResultDetails.innerHTML = '';
    }

    function renderTestError(message) {
        if (!testPanel) return;
        testPanel.className = 'config-test-panel failure';
        testResultBadge.textContent = '失败';
        testResultSummary.textContent = message;
        testResultDetails.innerHTML = '';
    }

    function renderTestResult(data) {
        if (!testPanel) return;

        const passed = Boolean(data.is_kill);
        testPanel.className = `config-test-panel ${passed ? 'success' : 'failure'}`;
        testResultBadge.textContent = passed ? '成功' : '失败';
        testResultSummary.textContent = passed
            ? `检测命中，置信度 ${formatPct(data.confidence)}`
            : `未达到命中条件，置信度 ${formatPct(data.confidence)}`;

        const details = data.details || {};
        const signals = data.signals || {};
        const booleans = data.booleans || {};
        const rules = details.rules || [];
        const warnings = data.warnings || [];

        const rows = [
            ['模式', data.mode === 'rules' ? '规则判定' : '加权判定'],
            ['预筛选', data.prefilter_passed ? '通过' : '未通过'],
            ['颜色', `${booleans.color ? '命中' : '未命中'} (${formatPct(details.color?.max_match_percent || 0)} 像素)`],
            ['模板', `${booleans.template ? '命中' : '未命中'} (${formatPct(signals.template || 0)})`],
            ['OCR', formatOcrResult(details.ocr, booleans.ocr)],
            ['YOLO', details.yolo?.available ? formatPct(signals.yolo || 0) : '未在助手测试中运行']
        ];

        let html = `
            <div class="test-result-grid">
                ${rows.map(([label, value]) => `
                    <div class="test-result-row">
                        <span>${escapeHtml(label)}</span>
                        <strong>${escapeHtml(value)}</strong>
                    </div>
                `).join('')}
            </div>
        `;

        if (rules.length > 0) {
            html += `
                <div class="test-section-title">规则结果</div>
                <div class="test-rule-list">
                    ${rules.map(rule => `
                        <div class="test-rule-item ${rule.matched ? 'matched' : 'missed'}">
                            <span>${escapeHtml(rule.name)}</span>
                            <strong>${rule.matched ? '命中' : `缺少: ${escapeHtml((rule.missing || []).join(', ') || '条件')}`}</strong>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        if (warnings.length > 0) {
            html += `
                <div class="test-warnings">
                    ${warnings.map(warning => `<div><i class="fas fa-triangle-exclamation"></i> ${escapeHtml(warning)}</div>`).join('')}
                </div>
            `;
        }

        testResultDetails.innerHTML = html;
    }

    function formatOcrResult(ocr, matched) {
        if (!ocr?.enabled) return '未启用';
        if (!ocr.available) return '不可用';
        if (matched) {
            const text = ocr.match?.text || ocr.match?.matched_keyword || '关键词';
            return `命中 ${text}`;
        }
        return `未命中 (${ocr.detections?.length || 0} 条文字)`;
    }

    function formatPct(value) {
        const num = Number(value) || 0;
        return `${(num * 100).toFixed(1)}%`;
    }

    function escapeHtml(value) {
        const div = document.createElement('div');
        div.textContent = String(value ?? '');
        return div.innerHTML;
    }
    
    function setCurrentRule(ruleName) {
        appState.currentRuleName = ruleName;
        
        // Dispatch event for tabs to update
        document.dispatchEvent(new CustomEvent('ruleChanged', { 
            detail: { ruleName } 
        }));
        
        // Update status indicator
        updateRuleIndicator();
    }

    function updateRuleIndicator() {
        // We reuse status-message for now, or we can add a dedicated indicator.
        // The requirements asked for "Status indicator showing '当前编辑: [rule_name]'"
        // Let's create/update a dedicated element if possible, or use the existing status area more effectively.
        // Actually, looking at index.html, there is a .status-indicator div wrapping #status-message.
        // I'll add a separate element for rule status in index.html, but here let's assume it exists.
        
        const ruleIndicator = document.getElementById('current-rule-indicator');
        if (ruleIndicator) {
            if (appState.currentRuleName) {
                ruleIndicator.textContent = `当前编辑: ${appState.currentRuleName}`;
                ruleIndicator.classList.add('rule-mode');
                ruleIndicator.style.display = 'inline-block';
            } else {
                ruleIndicator.textContent = '编辑全局配置';
                ruleIndicator.classList.remove('rule-mode');
                ruleIndicator.style.display = 'none'; // Hide when global to avoid clutter? Or show "Global"? 
                // Requirement says: "编辑全局" button to deselect.
                // Requirement says: Status indicator showing "当前编辑: [rule_name]" or "编辑全局配置"
                ruleIndicator.style.display = 'inline-block';
            }
        }
    }

    // Expose globally
    window.showStatus = showStatus;
    window.app = {
        showStatus,
        showLoading,
        hideLoading,
        get config() { return appState.config; },
        set config(val) { appState.config = val; },
        get imagePath() { return appState.currentImagePath; },
        get currentRuleName() { return appState.currentRuleName; },
        setCurrentRule
    };

    function showLoading(text = '正在处理...') {
        document.getElementById('loading-text').textContent = text;
        loadingOverlay.style.display = 'flex';
    }

    function hideLoading() {
        loadingOverlay.style.display = 'none';
    }

    // Start!
    init();
});
