/**
 * Config Preview Management
 */
class ConfigPreview {
    constructor() {
        this.panel = document.querySelector('.config-preview-bar');
        this.copyBtn = document.getElementById('copy-config');
        this.yamlDisplay = document.getElementById('config-yaml-preview');
        
        this.currentConfig = {};
        
        this.init();
    }

    init() {
        if (this.copyBtn) {
            this.copyBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.copyToClipboard();
            });
        }
        document.addEventListener('languageChanged', () => this.render());
    }

    update(config) {
        this.currentConfig = config;
        this.render();
    }

    render() {
        // Simple YAML conversion for preview
        // In a real app, we might use a library or get this from the backend
        const t = window.i18n ? window.i18n.t : (key) => key;
        let yaml = `${t('config.previewYamlHeader')}\n`;
        
        if (this.currentConfig.game) {
            yaml += `game: ${this.currentConfig.game}\n\n`;
        }

        if (this.currentConfig.detection) {
            yaml += "detection:\n";
            const d = this.currentConfig.detection;
            
            if (d.killfeed_roi) {
                yaml += `  killfeed_roi: [${d.killfeed_roi.join(', ')}]\n`;
            }
            
            if (d.ocr) {
                yaml += "  ocr:\n";
                yaml += `    enabled: ${d.ocr.enabled}\n`;
                yaml += `    keywords: [${d.ocr.keywords.map(k => `"${k}"`).join(', ')}]\n`;
                yaml += `    similarity_threshold: ${d.ocr.similarity_threshold}\n`;
            }

            if (d.templates) {
                yaml += "  templates:\n";
                for (const [name, info] of Object.entries(d.templates)) {
                    yaml += `    ${name}:\n`;
                    if (info.roi) {
                        yaml += `      roi: [${info.roi.join(', ')}]\n`;
                    }
                    if (info.path) {
                        yaml += `      path: "${info.path}"\n`;
                    }
                    yaml += `      threshold: ${info.threshold || 0.8}\n`;
                }
            }

            if (d.colors) {
                yaml += "  colors:\n";
                for (const [name, color] of Object.entries(d.colors)) {
                    yaml += `    ${name}:\n`;
                    if (color.hsv_lower) {
                        yaml += `      hsv_lower: [${color.hsv_lower.join(', ')}]\n`;
                    }
                    if (color.hsv_upper) {
                        yaml += `      hsv_upper: [${color.hsv_upper.join(', ')}]\n`;
                    }
                    if (color.tolerance !== undefined) {
                        yaml += `      tolerance: ${color.tolerance}\n`;
                    }
                }
            }
        }
        
        if (this.yamlDisplay) {
            this.yamlDisplay.textContent = yaml;
        }
    }

    async copyToClipboard() {
        try {
            const text = this.yamlDisplay ? this.yamlDisplay.textContent : '';
            if (!text) return;
            await navigator.clipboard.writeText(text);
            if (this.copyBtn) {
                const originalText = this.copyBtn.innerHTML;
                const t = window.i18n ? window.i18n.t : (key) => key;
                this.copyBtn.innerHTML = `<i class="fas fa-check"></i> ${t('config.copied')}`;
                setTimeout(() => {
                    this.copyBtn.innerHTML = originalText;
                }, 2000);
            }
        } catch (err) {
            console.error('Failed to copy!', err);
        }
    }
}

// Global instance
window.configPreview = new ConfigPreview();
