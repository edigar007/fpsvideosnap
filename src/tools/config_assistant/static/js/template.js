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

        // If a ROI is selected, send its coordinates for cropping
        if (this.roiHandler.selectedIndex !== -1) {
            const selectedRoi = this.roiHandler.rois[this.roiHandler.selectedIndex];
            // Get real coordinates from image data to avoid canvas scaling issues
            const imgWidth = this.appState.imageData.width;
            const imgHeight = this.appState.imageData.height;
            
            payload.roi = {
                x: Math.round(selectedRoi.x * imgWidth),
                y: Math.round(selectedRoi.y * imgHeight),
                w: Math.round(selectedRoi.w * imgWidth),
                h: Math.round(selectedRoi.h * imgHeight)
            };
            this.showStatus('正在保存裁剪后的模板...');
        } else {
            this.showStatus('正在保存完整图片为模板...');
        }

        try {
            const response = await fetch('/api/save-template', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            this.showStatus(`模板已保存: ${data.path}`, 'success');
        } catch (error) {
            console.error('Failed to save template:', error);
            this.showStatus('保存模板失败: ' + error.message, 'error');
        }
    }
}
