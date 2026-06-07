/**
 * Color Tab Logic
 * Handles color sampling, HSV ranges, and real-time masking preview.
 */
class ColorTab {
    constructor() {
        this.colorList = document.getElementById('color-sampler-list');
        this.startBtn = document.getElementById('start-color-sample');
        this.colors = {}; // { name: { hsv_lower, hsv_upper, tolerance } }

        this.init();
    }

    init() {
        if (this.startBtn) {
            this.startBtn.addEventListener('click', () => {
                alert('请在蓝框区域内点击要采样的像素点');
            });
        }

        document.addEventListener('colorSampled', (e) => {
            this.onColorSampled(e.detail.pos);
        });

        document.addEventListener('tabChanged', (e) => {
            if (e.detail.tabId === 'colors') {
                this.refreshList();
            } else if (window.canvasState) {
                window.canvasState.colorMask = null;
                window.canvasState.render();
            }
        });

        document.addEventListener('ruleChanged', (e) => {
            this.loadRuleColors(e.detail.ruleName);
        });
    }

    setColors(colors) {
        this.colors = colors || {};
        this.refreshList();
    }

    async onColorSampled(pos) {
        const game = document.getElementById('game-selector').value;
        if (!game) return alert('请先选择游戏');

        const imagePath = window.app?.imagePath;
        if (!imagePath) return alert('请先上传图片');

        if (!window.canvasState?.canvas) return;
        const canvas = window.canvasState.canvas;
        const x = pos.x / canvas.width;
        const y = pos.y / canvas.height;

        try {
            const response = await fetch('/api/color/pick', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image_path: imagePath,
                    x,
                    y,
                    tolerance: [20, 40, 40]
                })
            });

            if (!response.ok) {
                const err = await response.json();
                return alert('颜色采样失败: ' + (err.error || '未知错误'));
            }

            const data = await response.json();
            const name = prompt('请输入颜色名称 (如: kill_red, headshot_yellow):');
            if (!name) return;

            await this.addColor(name, data);
        } catch (err) {
            console.error('Color sample error:', err);
            alert('颜色采样失败');
        }
    }

    async addColor(name, sample) {
        const game = document.getElementById('game-selector').value;
        const tolerance = 20;

        const payload = {
            name: name,
            hsv: sample.hsv,
            hsv_lower: sample.hsv_range.lower,
            hsv_upper: sample.hsv_range.upper,
            tolerance: tolerance
        };

        const currentRule = window.app?.currentRuleName;
        if (currentRule) {
            payload.rule_name = currentRule;
        }

        try {
            const response = await fetch(`/api/config/${game}/colors`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const err = await response.json();
                return alert('添加颜色失败: ' + (err.error || '未知错误'));
            }

            const data = await response.json();
            this.syncColorsFromConfig(data.config, currentRule);
            this.refreshList();
            if (window.configPreview) window.configPreview.update(data.config);
        } catch (err) {
            console.error('Add color error:', err);
        }
    }

    refreshList() {
        if (!this.colorList) return;
        this.colorList.innerHTML = '';

        const names = Object.keys(this.colors);
        if (names.length === 0) {
            this.colorList.innerHTML = '<div class="empty-state">尚未创建颜色采样</div>';
            return;
        }

        names.forEach(name => {
            const colorData = this.colors[name];
            const item = document.createElement('div');
            item.className = 'color-item';

            const header = document.createElement('div');
            header.className = 'color-header';
            header.innerHTML = `
                <span class="color-name">${name}</span>
                <div class="color-actions">
                    <button class="icon-btn preview-btn" title="预览高亮"><i class="fas fa-eye"></i></button>
                    <button class="icon-btn delete-btn" title="删除"><i class="fas fa-trash"></i></button>
                </div>
            `;

            const body = document.createElement('div');
            body.className = 'color-body';

            const toleranceGroup = document.createElement('div');
            toleranceGroup.className = 'form-group mt-05';
            toleranceGroup.innerHTML = `
                <label>容差 (Tolerance): <span class="tol-val">${colorData.tolerance || 20}</span></label>
                <input type="range" class="tolerance-slider" min="5" max="100" value="${colorData.tolerance || 20}">
            `;

            const slider = toleranceGroup.querySelector('.tolerance-slider');
            const tolVal = toleranceGroup.querySelector('.tol-val');

            slider.oninput = (e) => {
                tolVal.textContent = e.target.value;
            };

            slider.onchange = (e) => {
                this.updateColorTolerance(name, parseInt(e.target.value, 10));
            };

            header.querySelector('.preview-btn').onclick = () => this.previewColor(name);
            header.querySelector('.delete-btn').onclick = () => this.deleteColor(name);

            item.appendChild(header);
            item.appendChild(body);
            body.appendChild(toleranceGroup);
            this.colorList.appendChild(item);
        });
    }

    async updateColorTolerance(name, tolerance) {
        const game = document.getElementById('game-selector').value;
        const payload = { tolerance };
        const currentRule = window.app?.currentRuleName;
        if (currentRule) {
            payload.rule_name = currentRule;
        }

        try {
            const response = await fetch(`/api/config/${game}/colors/${name}/tolerance`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const data = await response.json();
                this.syncColorsFromConfig(data.config, currentRule);
                this.refreshList();
                if (window.configPreview) window.configPreview.update(data.config);
                this.previewColor(name);
            }
        } catch (err) {
            console.error('Update color tolerance error:', err);
        }
    }

    async previewColor(name) {
        const roi = window.canvasState?.roi;
        const imagePath = window.app?.imagePath;

        if (!roi) return;
        if (!imagePath) return alert('请先上传图片');

        const color = this.colors[name];
        if (!color) return;

        try {
            const response = await fetch('/api/color/preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image_path: imagePath,
                    roi: roi,
                    lower: color.hsv_lower,
                    upper: color.hsv_upper
                })
            });

            if (response.ok) {
                const blob = await response.blob();
                const img = new Image();
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    canvas.width = img.width;
                    canvas.height = img.height;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0);
                    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);

                    window.canvasState.colorMask = imageData;
                    window.canvasState.render();
                    URL.revokeObjectURL(img.src);
                };
                img.src = URL.createObjectURL(blob);
            }
        } catch (err) {
            console.error('Preview color error:', err);
        }
    }

    async deleteColor(name) {
        if (!confirm(`确定要删除颜色 "${name}" 吗？`)) return;
        const game = document.getElementById('game-selector').value;

        const currentRule = window.app?.currentRuleName;
        let url = `/api/config/${game}/colors/${name}`;
        if (currentRule) {
            url += `?rule_name=${encodeURIComponent(currentRule)}`;
        }

        try {
            const response = await fetch(url, { method: 'DELETE' });

            if (response.ok) {
                const data = await response.json();
                this.syncColorsFromConfig(data.config, currentRule);
                this.refreshList();
                if (window.configPreview) window.configPreview.update(data.config);
                window.canvasState.colorMask = null;
                window.canvasState.render();
            }
        } catch (err) {
            console.error('Delete color error:', err);
        }
    }

    loadRuleColors(ruleName) {
        const config = window.app?.config;
        if (!config?.detection) return;

        let colors = config.detection.colors || {};

        if (ruleName) {
            const rules = config.detection.rules || [];
            const rule = rules.find(r => r.name === ruleName);
            if (rule?.detection_overrides?.colors) {
                colors = rule.detection_overrides.colors;
            }
        }

        this.setColors(colors);
        if (window.app?.showStatus) {
            window.app.showStatus(ruleName ? `已加载规则 ${ruleName} 的颜色` : '已加载全局颜色');
        }
    }

    syncColorsFromConfig(config, ruleName) {
        if (ruleName) {
            const rule = config.detection.rules.find(r => r.name === ruleName);
            this.colors = rule?.detection_overrides?.colors || {};
        } else {
            this.colors = config.detection.colors || {};
        }
        if (window.app) {
            window.app.config = config;
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.colorTab = new ColorTab();
});
