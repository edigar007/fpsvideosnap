const ocrTr = (key, params = {}) => window.i18n ? window.i18n.t(key, params) : key;

/**
 * OCR Tab Logic
 * Handles real-time OCR execution, keyword management, and testing.
 */
class OCRTab {
    constructor() {
        this.enabledCheck = document.getElementById('ocr-enabled');
        this.keywordsArea = document.getElementById('ocr-keywords');
        this.thresholdInput = document.getElementById('ocr-threshold');
        this.thresholdVal = document.getElementById('ocr-threshold-val');
        this.saveBtn = null; 
        this.resultsList = null; 
        this.testMatchBtn = null;

        this.ocrResults = []; // [{text, confidence, box}]
        
        this.init();
    }

    init() {
        if (this.thresholdInput) {
            this.thresholdInput.addEventListener('input', (e) => {
                this.thresholdVal.textContent = parseFloat(e.target.value).toFixed(2);
            });
        }

        document.addEventListener('tabChanged', (e) => {
            if (e.detail.tabId === 'ocr') {
                this.onTabActive();
            } else {
                // Clear highlights when leaving OCR tab
                if (window.canvasState) {
                    window.canvasState.tempHighlights = [];
                    window.canvasState.render();
                }
            }
        });

        document.addEventListener('ruleChanged', (e) => {
            this.loadRuleOCR(e.detail.ruleName);
        });

        this.setupUI();
        document.addEventListener('languageChanged', () => this.refreshLabels());
    }

    setupUI() {
        const tabPane = document.getElementById('tab-ocr');
        if (!tabPane) return;

        // Add Test Match Button
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'tab-actions mt-1';
        
        this.testMatchBtn = document.createElement('button');
        this.testMatchBtn.className = 'btn ghost full-width';
        this.testMatchBtn.innerHTML = `<i class="fas fa-vial"></i> ${ocrTr('config.addKeywordTest')}`;
        this.testMatchBtn.onclick = () => this.testMatching();
        actionsDiv.appendChild(this.testMatchBtn);

        tabPane.appendChild(actionsDiv);

        // Results Section
        this.resultsTitle = document.createElement('h4');
        this.resultsTitle.textContent = ocrTr('config.ocrResultsTitle');
        this.resultsTitle.className = 'mt-1';
        tabPane.appendChild(this.resultsTitle);

        this.resultsList = document.createElement('div');
        this.resultsList.className = 'ocr-results-list';
        this.resultsList.innerHTML = `<div class="empty-state">${ocrTr('config.ocrResultsEmpty')}</div>`;
        tabPane.appendChild(this.resultsList);

        // Save Button
        this.saveBtn = document.createElement('button');
        this.saveBtn.className = 'btn success full-width mt-1';
        this.saveBtn.innerHTML = `<i class="fas fa-save"></i> ${ocrTr('config.saveOcr')}`;
        this.saveBtn.onclick = () => this.saveOCR();
        tabPane.appendChild(this.saveBtn);
    }

    refreshLabels() {
        if (this.testMatchBtn) this.testMatchBtn.innerHTML = `<i class="fas fa-vial"></i> ${ocrTr('config.addKeywordTest')}`;
        if (this.resultsTitle) this.resultsTitle.textContent = ocrTr('config.ocrResultsTitle');
        if (this.saveBtn) this.saveBtn.innerHTML = `<i class="fas fa-save"></i> ${ocrTr('config.saveOcr')}`;
    }

    async onTabActive() {
        if (!window.canvasState || !window.canvasState.roi) {
            this.resultsList.innerHTML = `<div class="alert warning">${ocrTr('config.selectRoiFirst')}</div>`;
            return;
        }

        // Run OCR
        await this.runOCR();
    }

    async runOCR() {
        this.resultsList.innerHTML = `<div class="loading-inline"><i class="fas fa-spinner fa-spin"></i> ${ocrTr('config.runningOcr')}</div>`;
        
        const roi = window.canvasState.roi;
        const imagePath = window.app?.imagePath;
        
        if (!imagePath) {
            this.resultsList.innerHTML = `<div class="alert warning">${ocrTr('config.uploadImageFirst')}</div>`;
            return;
        }

        try {
            const response = await fetch('/api/ocr/detect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    image_path: imagePath,
                    roi: roi 
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.ocrResults = data.results || [];
                this.renderResults();
                if (this.ocrResults.length === 0) {
                    this.resultsList.innerHTML = `<div class="alert info">${ocrTr('config.noOcrText')}</div>`;
                }
            } else {
                const errorData = await response.json();
                this.resultsList.innerHTML = `<div class="alert error">${ocrTr('config.ocrFailed', { error: errorData.error || ocrTr('config.unknownError') })}</div>`;
            }
        } catch (err) {
            console.error('OCR Error:', err);
            this.resultsList.innerHTML = `<div class="alert error">${ocrTr('config.ocrDisconnected')}</div>`;
        }
    }

    renderResults() {
        if (this.ocrResults.length === 0) {
            this.resultsList.innerHTML = `<div class="empty-state">${ocrTr('config.noTextDetected')}</div>`;
            return;
        }

        this.resultsList.innerHTML = '';
        this.ocrResults.forEach(res => {
            const item = document.createElement('div');
            item.className = 'ocr-result-item';
            item.title = ocrTr('config.clickToAddKeyword');
            item.innerHTML = `
                <span class="text">${res.text}</span>
                <span class="conf">${(res.confidence * 100).toFixed(0)}%</span>
            `;
            item.onclick = () => this.addKeyword(res.text);
            this.resultsList.appendChild(item);
        });
    }

    addKeyword(text) {
        let current = this.keywordsArea.value.split(',').map(s => s.trim()).filter(s => s);
        // Remove common special chars
        const cleanText = text.replace(/[\[\]\(\)\{\}]/g, '');
        if (!current.includes(cleanText)) {
            current.push(cleanText);
            this.keywordsArea.value = current.join(', ');
            if (window.app && window.app.showStatus) window.app.showStatus(ocrTr('config.keywordAdded', { text: cleanText }));
        }
    }

    testMatching() {
        const keywords = this.keywordsArea.value.split(',').map(s => s.trim().toLowerCase()).filter(s => s);
        const threshold = parseFloat(this.thresholdInput.value);

        if (keywords.length === 0) return alert(ocrTr('config.keywordsRequired'));

        const matches = this.ocrResults.filter(res => {
            if (res.confidence < threshold) return false;
            return keywords.some(k => res.text.toLowerCase().includes(k));
        });

        if (window.canvasState) {
            window.canvasState.tempHighlights = matches
                .map(m => m.box)
                .filter(box => Array.isArray(box) && box.length === 4);
            window.canvasState.render();
            
            if (matches.length > 0) {
                alert(ocrTr('config.matchSuccess', { count: matches.length }));
            } else {
                alert(ocrTr('config.noKeywordMatch'));
            }
        }
    }

    async saveOCR() {
        const game = document.getElementById('game-selector').value;
        if (!game) return alert(ocrTr('config.selectGameFirst'));

        const config = {
            enabled: this.enabledCheck.checked,
            keywords: this.keywordsArea.value.split(',').map(s => s.trim()).filter(s => s),
            similarity_threshold: parseFloat(this.thresholdInput.value)
        };

        const currentRule = window.app?.currentRuleName;
        if (currentRule) {
            config.rule_name = currentRule;
        }

        try {
            const response = await fetch(`/api/config/${game}/ocr`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            if (response.ok) {
                const data = await response.json();
                if (window.app && window.app.showStatus) {
                    window.app.showStatus(ocrTr('config.ocrSaved'), 'success');
                } else {
                    alert(ocrTr('config.ocrSaved'));
                }
                if (window.configPreview && data.config) {
                    window.configPreview.update(data.config);
                } else if (window.configPreview) {
                    const configResponse = await fetch(`/api/config/${game}`);
                    if (configResponse.ok) {
                        const configData = await configResponse.json();
                        window.configPreview.update(configData);
                    }
                }
            } else {
                alert(ocrTr('config.saveFailed', { error: ocrTr('config.unknownError') }));
            }
        } catch (err) {
            console.error('Save OCR Error:', err);
            alert(ocrTr('config.networkError'));
        }
    }

    setConfig(config) {
        if (!config) return; // But allow clearing if empty/reset
        
        // Handle case where config might be null (e.g. override removed)
        // If config is provided, use it. If not, maybe defaults?
        // But loadRuleOCR handles the fallback logic.
        
        this.enabledCheck.checked = config.enabled !== false;
        this.keywordsArea.value = (config.keywords || []).join(', ');
        // Use similarity_threshold (YAML field) with fallback to threshold (legacy)
        const threshold = config.similarity_threshold ?? config.threshold ?? 0.8;
        this.thresholdInput.value = threshold;
        if (this.thresholdVal) this.thresholdVal.textContent = threshold.toFixed(2);
    }

    loadRuleOCR(ruleName) {
        const config = window.app?.config;
        if (!config?.detection) return;
        
        let ocr = config.detection.ocr || {}; // default global
        
        if (ruleName) {
            const rules = config.detection.rules || [];
            const rule = rules.find(r => r.name === ruleName);
            if (rule?.detection_overrides?.ocr) {
                // Merge overrides with global defaults or replace?
                // Typically overrides replace specific fields, but for object like OCR
                // it's usually a full replacement or merge. 
                // Let's assume merge for safety but usually UI shows the specific set.
                // If the user hasn't overridden OCR, we show global.
                ocr = { ...config.detection.ocr, ...rule.detection_overrides.ocr };
            }
        }
        
        this.setConfig(ocr);
        if (window.app?.showStatus) {
            window.app.showStatus(ruleName ? ocrTr('config.ruleLoadedOcr', { name: ruleName }) : ocrTr('config.globalLoadedOcr'));
        }
    }
}

// Initialize when DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.ocrTab = new OCRTab();
});
