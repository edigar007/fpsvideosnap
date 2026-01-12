/**
 * Template Management for Config Assistant
 */
class TemplateHandler {
    constructor(appState, roiHandler, showStatus) {
        this.appState = appState;
        this.roiHandler = roiHandler;
        this.showStatus = showStatus;

        this.gameInput = document.getElementById('game-name-input');
        this.templateInput = document.getElementById('template-name-input');
        this.saveBtn = document.getElementById('save-template-btn');

        this.initEvents();
    }

    initEvents() {
        this.saveBtn.addEventListener('click', () => this.saveTemplate());
        
        // Sync game name input with appState.currentGame
        this.gameInput.addEventListener('input', (e) => {
            this.appState.currentGame = e.target.value;
            document.getElementById('display-game-name').textContent = e.target.value || '-';
        });
    }

    setGameName(name) {
        this.gameInput.value = name;
        this.appState.currentGame = name;
    }

    async saveTemplate() {
        const gameName = this.gameInput.value.trim();
        const templateName = this.templateInput.value.trim();

        if (!gameName || !templateName) {
            this.showStatus('请输入游戏名称和模板名称', 'error');
            return;
        }

        if (!this.appState.imagePath) {
            this.showStatus('请先上传图片', 'error');
            return;
        }

        const payload = {
            image_path: this.appState.imagePath,
            game_name: gameName,
            template_name: templateName
        };

        // Prioritize using the cropRoi if in CROP mode
        let selectedRoi = null;
        if (this.roiHandler.mode === 'CROP' && this.roiHandler.cropRoi) {
            selectedRoi = this.roiHandler.cropRoi;
            this.showStatus('正在从截图选区保存模板...');
        } else if (this.roiHandler.selectedIndex !== -1) {
            // Fallback to detection ROI if one is selected
            selectedRoi = this.roiHandler.rois[this.roiHandler.selectedIndex];
            this.showStatus('正在从选中 ROI 保存模板...');
        } else {
            this.showStatus('正在保存完整图片为模板...');
        }

        if (selectedRoi) {
            // Get real coordinates from image data to avoid canvas scaling issues
            const imgWidth = this.appState.imageData.width;
            const imgHeight = this.appState.imageData.height;
            
            payload.roi = {
                x: Math.round(selectedRoi.x * imgWidth),
                y: Math.round(selectedRoi.y * imgHeight),
                w: Math.round(selectedRoi.w * imgWidth),
                h: Math.round(selectedRoi.h * imgHeight)
            };
        }

        try {
            const response = await fetch('/api/save-template', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            // Associate template with current configurations via AppState
            this.appState.addTemplate(templateName, data.path);

            this.showStatus(`模板已保存: ${data.path}`, 'success');

            // Reset mode and clear crop after successful save
            if (this.roiHandler.mode === 'CROP') {
                this.roiHandler.setMode('DETECTION');
                this.roiHandler.cropRoi = null;
            }
        } catch (error) {
            console.error('Failed to save template:', error);
            this.showStatus('保存模板失败: ' + error.message, 'error');
        }
    }
}
