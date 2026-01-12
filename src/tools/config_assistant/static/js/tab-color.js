/**
 * Color Tab Logic
 * Handles color sampling, HSV ranges, and real-time masking preview.
 */
class ColorTab {
    constructor() {
        this.colorList = document.getElementById('color-sampler-list');
        this.startBtn = document.getElementById('start-color-sample');
        this.colors = {}; // { name: { hsv_lower, hsv_upper, tolerance } }
        
        this.activeColor = null; // Currently being edited/sampled
        
        this.init();
    }

    init() {
        if (this.startBtn) {
            this.startBtn.addEventListener('click', () => {
                alert('请在蓝框区域内点击要采样的像素点');
            });
        }

        document.addEventListener('colorSampled', (e) => {
            this.onColorSampled(e.detail.pos, e.detail.inner);
        });

        document.addEventListener('tabChanged', (e) => {
            if (e.detail.tabId === 'colors') {
                this.refreshList();
            } else {
                // Clear highlight when leaving
                if (window.canvasState) {
                    window.canvasState.colorMask = null;
                    window.canvasState.render();
                }
            }
        });
    }

    setColors(colors) {
        this.colors = colors || {};
        this.refreshList();
    }

    async onColorSampled(pos, inner) {
        const game = document.getElementById('game-selector').value;
        if (!game) return alert('请先选择游戏');
        
        const imagePath = window.app?.imagePath;
        if (!imagePath) return alert('请先上传图片');

        try {
            const response = await fetch('/api/color/pick', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image_path: imagePath,
                    x: inner.x,
                    y: inner.y,
                    tolerance: [10, 50, 50]
                })
            });

            if (response.ok) {
                const data = await response.json();
                // data: { hsv: [h, s, v], rgb: [r, g, b] }
                const name = prompt('请输入颜色名称 (如: kill_red, headshot_yellow):');
                if (!name) return;

                await this.addColor(name, data.hsv);
            }
        } catch (err) {
            console.error('Color sample error:', err);
        }
    }

    async addColor(name, hsv) {
        const game = document.getElementById('game-selector').value;
        const tolerance = 20;
        const lower = [Math.max(0, hsv[0]-tolerance), Math.max(0, hsv[1]-tolerance*2), Math.max(0, hsv[2]-tolerance*2)];
        const upper = [Math.min(180, hsv[0]+tolerance), Math.min(255, hsv[1]+tolerance*2), Math.min(255, hsv[2]+tolerance*2)];

        try {
            const response = await fetch(`/api/config/${game}/colors`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name,
                    hsv_lower: lower,
                    hsv_upper: upper,
                    tolerance: tolerance
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.colors = data.config.detection.colors;
                this.refreshList();
                if (window.configPreview) window.configPreview.update(data.config);
            }
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
                this.updateColorTolerance(name, parseInt(e.target.value));
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
        try {
            const response = await fetch(`/api/config/${game}/colors/${name}/tolerance`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tolerance })
            });
            if (response.ok) {
                const data = await response.json();
                this.colors = data.config.detection.colors;
                if (window.configPreview) window.configPreview.update(data.config);
                // Auto refresh preview if it was active
                this.previewColor(name);
            }
        } catch (err) {
            console.error('Update color tolerance error:', err);
        }
    }

    async previewColor(name) {
        const game = document.getElementById('game-selector').value;
        const roi = window.canvasState.roi;
        const imagePath = window.app?.imagePath;
        
        if (!roi) return;
        if (!imagePath) return alert('请先上传图片');
        
        const color = this.colors[name];
        if (!color) return;

        try {
            const response = await fetch(`/api/color/preview`, {
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
                    // Create ImageData from Blob
                    const canvas = document.createElement('canvas');
                    canvas.width = img.width;
                    canvas.height = img.height;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0);
                    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                    
                    window.canvasState.colorMask = imageData;
                    window.canvasState.render();
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
        try {
            const response = await fetch(`/api/config/${game}/colors/${name}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                const data = await response.json();
                this.colors = data.config.detection.colors;
                this.refreshList();
                if (window.configPreview) window.configPreview.update(data.config);
                window.canvasState.colorMask = null;
                window.canvasState.render();
            }
        } catch (err) {
            console.error('Delete color error:', err);
        }
    }
}

// Initialize when DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.colorTab = new ColorTab();
});
