const templateTr = (key, params = {}) => window.i18n ? window.i18n.t(key, params) : key;

/**
 * Template Tab Logic
 * Handles capturing, listing, and managing icon templates.
 */
class TemplateTab {
    constructor() {
        this.templateList = document.getElementById('template-list');
        this.addBtn = document.getElementById('add-template-btn');
        this.templates = {}; // { name: { roi, threshold } }
        
        this.init();
    }

    init() {
        if (this.addBtn) {
            this.addBtn.addEventListener('click', () => this.captureTemplate());
        }

        document.addEventListener('subRoiSelected', (e) => {
            this.onSubRoiSelected(e.detail.subRoi);
        });

        document.addEventListener('tabChanged', (e) => {
            if (e.detail.tabId === 'templates') {
                this.refreshList();
            }
        });

        document.addEventListener('ruleChanged', (e) => {
            this.loadRuleTemplates(e.detail.ruleName);
        });

        document.addEventListener('languageChanged', () => this.refreshList());
    }

    setTemplates(templates) {
        this.templates = templates || {};
        this.refreshList();
    }

    onSubRoiSelected(subRoi) {
        if (!subRoi) return;
        
        const name = prompt(templateTr('config.templateNamePrompt'));
        if (!name) {
            window.canvasState.subRoi = null;
            window.canvasState.render();
            return;
        }

        this.addTemplate(name, subRoi);
    }

    async addTemplate(name, subRoi) {
        const game = document.getElementById('game-selector').value;
        if (!game) return alert(templateTr('config.selectGameFirst'));
        
        const imagePath = window.app?.imagePath;
        if (!imagePath) return alert(templateTr('config.uploadImageFirst'));
        
        // Convert subRoi (relative to ROI) to absolute (relative to image)
        const roi = window.canvasState.roi;
        if (!roi) return alert(templateTr('config.mainRoiFirst'));
        
        const [rx, ry, rw, rh] = roi;
        const [sx, sy, sw, sh] = subRoi;
        const absoluteSubRoi = [
            rx + sx * rw,  // x
            ry + sy * rh,  // y
            sw * rw,       // w
            sh * rh        // h
        ];

        try {
            // First, crop and save the template image
            const cropResponse = await fetch('/api/template/crop', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image_path: imagePath,
                    game: game,
                    name: name,
                    roi: null,  // Not needed, using absolute coordinates
                    sub_roi: absoluteSubRoi
                })
            });
            
            if (!cropResponse.ok) {
                const cropErr = await cropResponse.json();
                return alert(templateTr('config.cropTemplateFailed', { error: cropErr.error || templateTr('config.unknownError') }));
            }
            
            const cropData = await cropResponse.json();
            const templatePath = cropData.path;
            
            // Then, add to config
            const payload = {
                name: name,
                roi: subRoi,
                path: templatePath,
                threshold: 0.8
            };

            const currentRule = window.app?.currentRuleName;
            if (currentRule) {
                payload.rule_name = currentRule;
            }

            const response = await fetch(`/api/config/${game}/templates`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const data = await response.json();
                // Update local templates from response
                if (currentRule) {
                     const rule = data.config.detection.rules.find(r => r.name === currentRule);
                     this.templates = rule.detection_overrides?.templates || {};
                } else {
                     this.templates = data.config.detection.templates;
                }
                
                this.refreshList();
                if (window.configPreview) window.configPreview.update(data.config);
                window.canvasState.subRoi = null;
                window.canvasState.render();
            } else {
                const err = await response.json();
                alert(templateTr('config.addTemplateFailed', { error: err.error || templateTr('config.unknownError') }));
            }
        } catch (err) {
            console.error('Add template error:', err);
        }
    }

    async captureTemplate() {
        if (!window.canvasState || !window.canvasState.roi) {
            return alert(templateTr('config.mainRoiFirst'));
        }
        alert(templateTr('config.dragInsideRoi'));
    }

    refreshList() {
        if (!this.templateList) return;
        this.templateList.innerHTML = '';

        const names = Object.keys(this.templates);
        if (names.length === 0) {
            this.templateList.innerHTML = `<div class="empty-state">${templateTr('config.noTemplates')}</div>`;
            return;
        }

        names.forEach(name => {
            const temp = this.templates[name];
            const item = document.createElement('div');
            item.className = 'template-item';
            
            // Thumbnail container
            const thumb = document.createElement('div');
            thumb.className = 'template-thumb';
            // In a real app, we might want to fetch the actual cropped image
            // For now, we'll just show the name and ROI info
            thumb.innerHTML = `<i class="fas fa-image"></i>`;

            const info = document.createElement('div');
            info.className = 'template-info';
            const roiText = temp.roi && Array.isArray(temp.roi) 
                ? `ROI: [${temp.roi.map(v => v.toFixed(2)).join(', ')}]`
                : templateTr('config.templateRoiUnset');
            info.innerHTML = `
                <div class="template-name">${name}</div>
                <div class="template-meta">${roiText}</div>
            `;

            const controls = document.createElement('div');
            controls.className = 'template-controls';
            
            const thresholdInput = document.createElement('input');
            thresholdInput.type = 'number';
            thresholdInput.min = 0;
            thresholdInput.max = 1;
            thresholdInput.step = 0.05;
            thresholdInput.value = temp.threshold || 0.8;
            thresholdInput.title = templateTr('config.matchThreshold');
            thresholdInput.onchange = (e) => this.updateThreshold(name, parseFloat(e.target.value));

            const delBtn = document.createElement('button');
            delBtn.className = 'icon-btn delete';
            delBtn.innerHTML = '<i class="fas fa-trash"></i>';
            delBtn.onclick = () => this.deleteTemplate(name);

            controls.appendChild(thresholdInput);
            controls.appendChild(delBtn);

            item.appendChild(thumb);
            item.appendChild(info);
            item.appendChild(controls);
            this.templateList.appendChild(item);
        });
    }

    async updateThreshold(name, threshold) {
        const game = document.getElementById('game-selector').value;
        
        const payload = { threshold };
        const currentRule = window.app?.currentRuleName;
        if (currentRule) {
            payload.rule_name = currentRule;
        }

        try {
            const response = await fetch(`/api/config/${game}/templates/${name}/threshold`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                const data = await response.json();
                if (window.configPreview) window.configPreview.update(data.config);
                // Also update local state
                if (this.templates[name]) {
                    this.templates[name].threshold = threshold;
                }
            }
        } catch (err) {
            console.error('Update threshold error:', err);
        }
    }

    async deleteTemplate(name) {
        if (!confirm(templateTr('config.deleteTemplateConfirm', { name }))) return;

        const game = document.getElementById('game-selector').value;
        
        // For DELETE, usually params are in URL, but we need rule_name.
        // If API supports query param? Or body?
        // Standard REST DELETE usually doesn't have body, but many servers allow it.
        // Alternatively, use query param. Let's assume query param or body.
        // Task 4 didn't specify DELETE changes, but backend likely supports it if using same mixin.
        // Let's try query param first as it's safer for DELETE.
        
        const currentRule = window.app?.currentRuleName;
        let url = `/api/config/${game}/templates/${name}`;
        if (currentRule) {
            url += `?rule_name=${encodeURIComponent(currentRule)}`;
        }

        try {
            const response = await fetch(url, {
                method: 'DELETE'
            });

            if (response.ok) {
                const data = await response.json();
                
                if (currentRule) {
                    const rule = data.config.detection.rules.find(r => r.name === currentRule);
                    this.templates = rule.detection_overrides?.templates || {};
                } else {
                    this.templates = data.config.detection.templates;
                }
                
                this.refreshList();
                if (window.configPreview) window.configPreview.update(data.config);
            }
        } catch (err) {
            console.error('Delete template error:', err);
        }
    }

    loadRuleTemplates(ruleName) {
        const config = window.app?.config;
        if (!config?.detection) return;
        
        let templates = config.detection.templates || {}; // default global
        
        if (ruleName) {
            const rules = config.detection.rules || [];
            const rule = rules.find(r => r.name === ruleName);
            if (rule?.detection_overrides?.templates) {
                templates = rule.detection_overrides.templates;
            }
        }
        
        this.setTemplates(templates);
        if (window.app?.showStatus) {
            window.app.showStatus(ruleName ? templateTr('config.ruleLoadedTemplates', { name: ruleName }) : templateTr('config.globalLoadedTemplates'));
        }
    }
}

// Initialize when DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.templateTab = new TemplateTab();
});
