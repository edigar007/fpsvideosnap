/**
 * ROI Tab Logic
 * Handles ROI drawing feedback, coordinates display, and preview.
 */
class ROITab {
    constructor() {
        this.inputs = {
            x: document.getElementById('roi-x'),
            y: document.getElementById('roi-y'),
            w: document.getElementById('roi-w'),
            h: document.getElementById('roi-h')
        };
        this.previewCanvas = document.getElementById('roi-preview-canvas');
        if (this.previewCanvas) {
            this.previewCtx = this.previewCanvas.getContext('2d');
        }
        this.saveBtn = document.getElementById('save-roi-btn');

        this.init();
    }

    init() {
        // Listen for ROI changes from canvas-state
        document.addEventListener('roiChanged', (e) => {
            this.updateFields(e.detail.roi);
        });

        document.addEventListener('roiSelected', (e) => {
            this.updatePreview(e.detail.roi);
        });

        document.addEventListener('ruleChanged', (e) => {
            this.loadRuleROI(e.detail.ruleName);
        });

        if (this.saveBtn) {
            this.saveBtn.addEventListener('click', () => this.saveROI());
        }
    }

    updateFields(roi) {
        if (!roi) return;
        this.inputs.x.value = roi[0].toFixed(4);
        this.inputs.y.value = roi[1].toFixed(4);
        this.inputs.w.value = roi[2].toFixed(4);
        this.inputs.h.value = roi[3].toFixed(4);
    }

    updatePreview(roi) {
        if (!roi || !this.previewCanvas || !window.canvasState || !window.canvasState.image) return;
        
        const [rx, ry, rw, rh] = roi;
        if (rw <= 0 || rh <= 0) return;

        const img = window.canvasState.image;
        const px = rx * img.width;
        const py = ry * img.height;
        const pw = rw * img.width;
        const ph = rh * img.height;

        // Reset canvas size to match aspect ratio of ROI but fixed width
        const displayW = this.previewCanvas.width;
        const displayH = (ph / pw) * displayW;
        this.previewCanvas.height = Math.min(displayH, 150); // Cap height

        this.previewCtx.clearRect(0, 0, this.previewCanvas.width, this.previewCanvas.height);
        
        // Draw cropped ROI
        this.previewCtx.drawImage(
            img, 
            px, py, pw, ph, 
            0, 0, this.previewCanvas.width, this.previewCanvas.height
        );
    }

    async saveROI() {
        const roi = window.canvasState.roi;
        if (!roi) return alert('请先在画布上选择区域');

        const game = document.getElementById('game-selector').value;
        if (!game) return alert('请选择游戏');

        const payload = { roi: this.roi || roi };
        const currentRule = window.app?.currentRuleName;
        if (currentRule) {
            payload.rule_name = currentRule;
        }

        try {
            const response = await fetch(`/api/config/${game}/roi`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const data = await response.json();
                if (window.showStatus) {
                    window.showStatus('ROI 已成功保存到配置', 'success');
                } else {
                    alert('ROI 已成功保存到配置');
                }
                
                // Trigger preview update
                if (window.configPreview && data.config) {
                    window.configPreview.update(data.config);
                } else if (window.configPreview) {
                    // If config not returned, reload it
                    const game = document.getElementById('game-selector').value;
                    const configResponse = await fetch(`/api/config/${game}`);
                    if (configResponse.ok) {
                        const configData = await configResponse.json();
                        window.configPreview.update(configData);
                    }
                }
            } else {
                const err = await response.json();
                alert('保存失败: ' + (err.error || '未知错误'));
            }
        } catch (err) {
            console.error('Save ROI Error:', err);
            alert('无法保存 ROI，切检查后端服务是否正常');
        }
    }

    /**
     * Load ROI from config into UI
     */
    setROI(roi) {
        if (!roi) return;
        this.updateFields(roi);
        this.updatePreview(roi);
        if (window.canvasState) {
            window.canvasState.roi = roi;
            window.canvasState.render();
        }
    }

    loadRuleROI(ruleName) {
        const config = window.app?.config;
        if (!config?.detection) return;
        
        let roi = config.detection.killfeed_roi; // default global
        
        if (ruleName) {
            const rules = config.detection.rules || [];
            const rule = rules.find(r => r.name === ruleName);
            if (rule?.detection_overrides?.killfeed_roi) {
                roi = rule.detection_overrides.killfeed_roi;
            }
        }
        
        // If we found an ROI (global or override), update. 
        // If override doesn't exist, we fallback to global (default behavior logic)
        // OR should we show empty if not overridden? 
        // Requirement says "fallback to global if none"
        
        this.setROI(roi);
        if (window.app?.showStatus) {
            window.app.showStatus(ruleName ? `已加载规则 ${ruleName} 的 ROI` : '已加载全局 ROI');
        }
    }
}

// Initialize when DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.roiTab = new ROITab();
});
