/**
 * Main application logic for Config Assistant
 */

document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const canvasContainer = document.getElementById('canvas-container');
    const gameSelector = document.getElementById('game-selector');
    const displayGameName = document.getElementById('display-game-name');
    const statusMessage = document.getElementById('status-message');
    const loadingOverlay = document.getElementById('loading-overlay');
    const yamlPreview = document.getElementById('yaml-preview');
    
    // Tools
    const toolRoiBtn = document.getElementById('tool-roi');
    const toolColorBtn = document.getElementById('tool-color');
    
    const roiList = document.getElementById('roi-list');
    const colorList = document.getElementById('color-list');
    const clearRoiBtn = document.getElementById('clear-roi');
    const clearColorsBtn = document.getElementById('clear-colors');

    // State
    const appState = {
        imagePath: null,
        currentFile: null,
        currentGame: '',
        activeTool: 'roi', // 'roi' or 'color'
        rois: [], // list of {name, x, y, h, w}
        colors: [], // list of hsv objects
        imageData: null,
        showColorHighlight: true,
        yamlOutput: ''
    };

    // History
    const history = new HistoryManager();

    const pushHistory = () => {
        history.push({
            rois: appState.rois,
            colors: appState.colors
        });
    };

    // Initialize Canvas
    const imgCanvas = new ImageCanvas('main-canvas', 'canvas-container');
    const roiHandler = new ROIHandler(document.getElementById('main-canvas'), imgCanvas, () => {
        appState.rois = roiHandler.rois;
        updateRoiUI();
        throttledUpdateYaml();
        pushHistory();
    });

    const colorPicker = new ColorPickerHandler(
        document.getElementById('main-canvas'), 
        imgCanvas, 
        appState, 
        () => {
            updateColorUI();
            throttledUpdateYaml();
            pushHistory();
        }
    );

    const showStatus = (msg, type = 'info') => {
        statusMessage.textContent = msg;
        statusMessage.className = 'status-msg ' + type;
        console.log(`[${type}] ${msg}`);
    };

    const templateHandler = new TemplateHandler(appState, roiHandler, showStatus);

    imgCanvas.onDraw = (ctx) => {
        roiHandler.render();
        colorPicker.render(ctx);
    };

    // --- Init ---
    fetchGames();
    updateYamlPreview();
    pushHistory(); // Push initial state

    // --- Event Listeners ---
    
    // File Selection
    dropZone.addEventListener('click', () => fileInput.click());
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            handleFileSelection(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelection(e.target.files[0]);
        }
    });

    const downloadBtn = document.getElementById('download-config');
    const copyYamlBtn = document.getElementById('copy-yaml');
    const saveConfigBtn = document.getElementById('save-config');

    // Tool Selection
    toolRoiBtn.addEventListener('click', () => setActiveTool('roi'));
    toolColorBtn.addEventListener('click', () => setActiveTool('color'));

    // Game Selection
    gameSelector.addEventListener('change', (e) => {
        appState.currentGame = e.target.value;
        displayGameName.textContent = appState.currentGame || '-';
        templateHandler.setGameName(appState.currentGame);
        if (appState.currentGame) {
            loadGameConfig(appState.currentGame);
        }
    });

    // Action Buttons
    copyYamlBtn.addEventListener('click', () => {
        if (!appState.yamlOutput) return;
        navigator.clipboard.writeText(appState.yamlOutput).then(() => {
            showStatus('已复制到剪贴板', 'success');
        });
    });

    downloadBtn.addEventListener('click', () => {
        if (!appState.yamlOutput) return;
        const blob = new Blob([appState.yamlOutput], { type: 'text/yaml' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${appState.currentGame || 'config'}.yaml`;
        a.click();
        URL.revokeObjectURL(url);
    });

    saveConfigBtn.addEventListener('click', async () => {
        if (!appState.yamlOutput || !appState.currentGame) {
            showStatus('没有可保存的配置或游戏名称', 'error');
            return;
        }

        try {
            const response = await fetch('/api/save-config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    game_name: appState.currentGame,
                    yaml: appState.yamlOutput
                })
            });
            const data = await response.json();
            if (data.error) throw new Error(data.error);
            showStatus(`配置已保存到 ${data.path}`, 'success');
        } catch (error) {
            showStatus('保存失败: ' + error.message, 'error');
        }
    });

    // Clear Buttons
    clearRoiBtn.addEventListener('click', () => {
        roiHandler.clearAll();
    });

    clearColorsBtn.addEventListener('click', () => {
        appState.colors = [];
        updateColorUI();
        updateYamlPreview();
    });

    // --- Actions ---

    async function fetchGames() {
        try {
            const response = await fetch('/api/games');
            const games = await response.json();
            
            gameSelector.innerHTML = '<option value="">选择游戏...</option>';
            games.forEach(game => {
                const option = document.createElement('option');
                option.value = game;
                option.textContent = game;
                gameSelector.appendChild(option);
            });
        } catch (error) {
            console.error('Failed to fetch games:', error);
            showStatus('获取游戏列表失败', 'error');
        }
    }

    async function handleFileSelection(file) {
        if (!file.type.startsWith('image/')) {
            showStatus('请上传图片文件', 'error');
            return;
        }

        showLoading(true);
        appState.currentFile = file;

        try {
            // 1. Upload to server
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            if (data.error) throw new Error(data.error);
            
            appState.imagePath = data.path;
            appState.imageData = data;

            // 2. Load into canvas
            await imgCanvas.loadImage(file);
            
            // 3. Update UI
            dropZone.style.display = 'none';
            canvasContainer.style.display = 'block';
            
            // 4. Resize canvas after container is visible
            imgCanvas.resize();
            
            showStatus('图片加载成功');
            
        } catch (error) {
            console.error('Upload failed:', error);
            showStatus('文件处理失败: ' + error.message, 'error');
        } finally {
            showLoading(false);
        }
    }

    function setActiveTool(tool) {
        appState.activeTool = tool;
        toolRoiBtn.classList.toggle('active', tool === 'roi');
        toolColorBtn.classList.toggle('active', tool === 'color');
        
        roiHandler.enabled = (tool === 'roi');
        colorPicker.setEnabled(tool === 'color');
        
        showStatus(`当前工具: ${tool === 'roi' ? 'ROI 选择' : '颜色拾取'}`);
    }

    async function loadGameConfig(gameName) {
        try {
            showStatus(`正在加载 ${gameName} 的配置...`);
            const response = await fetch(`/api/load-config/${gameName}`);
            const config = await response.json();
            if (config.error) throw new Error(config.error);
            
            // Populating ROIs
            roiHandler.rois = [];
            if (config.detection) {
                for (const [key, value] of Object.entries(config.detection)) {
                    if (key.endsWith('_roi') && Array.isArray(value) && value.length === 4) {
                        const name = key.replace('_roi', '');
                        roiHandler.rois.push({
                            name: name,
                            x: value[0], y: value[1], w: value[2], h: value[3]
                        });
                    }
                }
            }
            appState.rois = roiHandler.rois;
            updateRoiUI();

            // Populating Colors
            appState.colors = [];
            if (config.detection && config.detection.colors) {
                for (const [name, range] of Object.entries(config.detection.colors)) {
                    appState.colors.push({
                        name: name,
                        lower: range.lower,
                        upper: range.upper,
                        rgb: [128, 128, 128] // Placeholder RGB if not available
                    });
                }
            }
            updateColorUI();
            
            updateYamlPreview();
            showStatus(`${gameName} 配置加载成功`, 'success');
        } catch (error) {
            console.warn('Could not load existing config:', error);
            showStatus('加载现有配置失败', 'error');
        }
    }

    function updateRoiUI() {
        if (appState.rois.length === 0) {
            roiList.innerHTML = '<div class="empty-msg">暂无 ROI</div>';
            return;
        }
        
        roiList.innerHTML = appState.rois.map((roi, i) => `
            <div class="data-item ${roiHandler.selectedIndex === i ? 'selected' : ''}" onclick="window.selectROI(${i})">
                <div class="roi-info">
                    <input type="text" class="roi-name-edit" value="${roi.name}" 
                        onchange="window.renameROI(${i}, this.value)" 
                        onclick="event.stopPropagation()">
                    <span class="code">[${roi.x.toFixed(3)}, ${roi.y.toFixed(3)}, ${roi.w.toFixed(3)}, ${roi.h.toFixed(3)}]</span>
                </div>
                <button class="remove-btn" onclick="window.removeROI(${i}, event)">&times;</button>
            </div>
        `).join('');
    }

    // Expose functions to window for onclick handlers
    window.selectROI = (index) => {
        roiHandler.selectedIndex = index;
        imgCanvas.draw();
        updateRoiUI();
    };

    window.renameROI = (index, newName) => {
        if (roiHandler.rois[index]) {
            roiHandler.rois[index].name = newName;
            updateRoiUI();
            imgCanvas.draw();
            updateYamlPreview();
        }
    };

    window.removeROI = (index, event) => {
        if (event) event.stopPropagation();
        roiHandler.rois.splice(index, 1);
        if (roiHandler.selectedIndex === index) roiHandler.selectedIndex = -1;
        else if (roiHandler.selectedIndex > index) roiHandler.selectedIndex--;
        
        roiHandler.onUpdate();
        imgCanvas.draw();
    };

    function updateColorUI() {
        if (appState.colors.length === 0) {
            colorList.innerHTML = '<div class="empty-msg">暂无颜色</div>';
            return;
        }

        colorList.innerHTML = appState.colors.map((c, i) => `
            <div class="data-item ${colorPicker.selectedColorIndex === i ? 'selected' : ''}" 
                onclick="window.selectColor(${i})">
                <div class="color-swatch" style="background-color: rgb(${c.rgb.join(',')})"></div>
                <div class="roi-info">
                    <span class="roi-name">${c.name}</span>
                    <span class="code">HSV Lower: [${c.lower.join(',')}]</span>
                    <span class="code">HSV Upper: [${c.upper.join(',')}]</span>
                </div>
                <button class="remove-btn" onclick="window.removeColor(${i}, event)">&times;</button>
            </div>
        `).join('');
    }

    window.selectColor = (index) => {
        colorPicker.selectedColorIndex = index;
        const color = appState.colors[index];
        if (color) {
            colorPicker.currentColor = {...color};
            colorPicker.showColorDetails(colorPicker.currentColor);
            // Toggle highlight
            appState.showColorHighlight = true;
        }
        updateColorUI();
        imgCanvas.draw();
    };

    window.removeColor = (index, event) => {
        if (event) event.stopPropagation();
        appState.colors.splice(index, 1);
        if (colorPicker.selectedColorIndex === index) {
            colorPicker.selectedColorIndex = -1;
            colorPicker.panel.style.display = 'none';
        } else if (colorPicker.selectedColorIndex > index) {
            colorPicker.selectedColorIndex--;
        }
        updateColorUI();
        updateYamlPreview();
        imgCanvas.draw();
    };

    async function updateYamlPreview() {
        if (appState.rois.length === 0 && appState.colors.length === 0) {
            yamlPreview.textContent = '# 待生成的配置...';
            appState.yamlOutput = '';
            return;
        }

        try {
            const response = await fetch('/api/generate-config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    game_name: appState.currentGame || 'unknown',
                    rois: appState.rois,
                    colors: appState.colors
                })
            });
            const data = await response.json();
            if (data.yaml) {
                appState.yamlOutput = data.yaml;
                yamlPreview.textContent = data.yaml;
            }
        } catch (error) {
            console.error('Failed to generate YAML:', error);
        }
    }

    // --- Helpers ---

    function throttle(func, wait) {
        let timeout = null;
        return function(...args) {
            if (!timeout) {
                timeout = setTimeout(() => {
                    func.apply(this, args);
                    timeout = null;
                }, wait);
            }
        };
    }

    const throttledUpdateYaml = throttle(updateYamlPreview, 500);

    // --- Keyboard Shortcuts ---
    window.addEventListener('keydown', (e) => {
        // Ignore if typing in input
        if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
            if (e.key === 'Escape') document.activeElement.blur();
            return;
        }

        const key = e.key.toLowerCase();
        const ctrl = e.ctrlKey || e.metaKey;

        if (key === 'r') setActiveTool('roi');
        if (key === 'c') setActiveTool('color');
        if (key === 'delete' || key === 'backspace') {
            if (appState.activeTool === 'roi' && roiHandler.selectedIndex !== -1) {
                window.removeROI(roiHandler.selectedIndex);
            } else if (appState.activeTool === 'color' && colorPicker.selectedColorIndex !== -1) {
                window.removeColor(colorPicker.selectedColorIndex);
            }
        }
        if (key === 'escape') {
            if (appState.activeTool === 'roi') roiHandler.selectedIndex = -1;
            if (appState.activeTool === 'color') colorPicker.cancelPicker();
            imgCanvas.draw();
        }

        // Undo/Redo
        if (ctrl && key === 'z') {
            e.preventDefault();
            const prevState = history.undo();
            if (prevState) {
                applyHistorySnapshot(prevState);
                showStatus('撤销成功');
            }
        }
        if (ctrl && key === 'y' || (ctrl && e.shiftKey && key === 'z')) {
            e.preventDefault();
            const nextState = history.redo();
            if (nextState) {
                applyHistorySnapshot(nextState);
                showStatus('重做成功');
            }
        }
    });

    function applyHistorySnapshot(snapshot) {
        appState.rois = JSON.parse(JSON.stringify(snapshot.rois));
        appState.colors = JSON.parse(JSON.stringify(snapshot.colors));
        
        roiHandler.rois = appState.rois;
        colorPicker.rois = appState.rois; // if needed
        
        updateRoiUI();
        updateColorUI();
        updateYamlPreview();
        imgCanvas.draw();
    }

    function showLoading(show) {
        loadingOverlay.style.display = show ? 'flex' : 'none';
    }
});
