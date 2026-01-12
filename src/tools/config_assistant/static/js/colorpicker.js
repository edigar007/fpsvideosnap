/**
 * Color Picking and Management for Config Assistant
 */
class ColorPickerHandler {
    constructor(canvas, imageCanvas, appState, onUpdate) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.imageCanvas = imageCanvas;
        this.appState = appState;
        this.onUpdate = onUpdate;
        this.enabled = false;
        
        this.currentColor = null; // { rgb, hsv, name, tolerance }
        this.selectedColorIndex = -1;

        this.initElements();
        this.initEvents();
    }

    initElements() {
        this.panel = document.getElementById('color-picker-details');
        this.preview = this.panel.querySelector('.color-preview-box');
        this.rgbText = this.panel.querySelector('.rgb-value');
        this.hsvText = this.panel.querySelector('.hsv-value');
        this.nameInput = this.panel.querySelector('#color-name-input');
        this.toleranceSlider = this.panel.querySelector('#color-tolerance');
        this.toleranceValue = this.panel.querySelector('.tolerance-value');
        this.lowerText = this.panel.querySelector('.hsv-lower');
        this.upperText = this.panel.querySelector('.hsv-upper');
        this.saveBtn = this.panel.querySelector('#save-color-btn');
        this.cancelBtn = this.panel.querySelector('#cancel-color-btn');
        this.highlightToggle = this.panel.querySelector('#toggle-highlight');
    }

    initEvents() {
        this.canvas.addEventListener('click', this.handleClick.bind(this));
        
        this.toleranceSlider.addEventListener('input', (e) => {
            if (this.currentColor) {
                this.currentColor.tolerance = parseInt(e.target.value);
                this.toleranceValue.textContent = this.currentColor.tolerance;
                this.updateHsvBounds(this.currentColor);
            }
        });

        this.highlightToggle.addEventListener('change', (e) => {
            this.appState.showColorHighlight = e.target.checked;
            if (this.appState.showColorHighlight) {
                this.generateHighlightMask();
            } else {
                this.mask = null;
                this.imageCanvas.draw();
            }
        });

        this.saveBtn.addEventListener('click', () => this.saveCurrentColor());
        this.cancelBtn.addEventListener('click', () => {
            this.panel.style.display = 'none';
            this.currentColor = null;
        });
    }

    setEnabled(enabled) {
        this.enabled = enabled;
        if (enabled) {
            this.canvas.style.cursor = 'crosshair';
        } else {
            this.canvas.style.cursor = 'default';
        }
    }

    async handleClick(e) {
        if (!this.enabled || !this.imageCanvas.image || !this.appState.imagePath) return;

        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Get real image coordinates
        const real = this.imageCanvas.getRealCoords(x, y);

        try {
            const response = await fetch('/api/pick-color', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image_path: this.appState.imagePath,
                    x: real.x,
                    y: real.y
                })
            });

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            this.currentColor = {
                rgb: data.rgb,
                hsv: data.hsv,
                name: 'new_color',
                tolerance: 20
            };

            this.showColorDetails(this.currentColor);
        } catch (error) {
            console.error('Failed to pick color:', error);
            // In a real app we'd show a status message via appState
        }
    }

    showColorDetails(color) {
        this.panel.style.display = 'block';
        this.preview.style.backgroundColor = `rgb(${color.rgb[0]}, ${color.rgb[1]}, ${color.rgb[2]})`;
        this.rgbText.textContent = `RGB: ${color.rgb.join(', ')}`;
        this.hsvText.textContent = `HSV: ${color.hsv.join(', ')}`;
        this.nameInput.value = color.name;
        this.toleranceSlider.value = color.tolerance;
        this.toleranceValue.textContent = color.tolerance;
        this.highlightToggle.checked = this.appState.showColorHighlight;

        this.updateHsvBounds(color);
    }

    updateHsvBounds(color) {
        const tol = color.tolerance;
        const h = color.hsv[0];
        const s = color.hsv[1];
        const v = color.hsv[2];

        // OpenCV HSV bounds: H: 0-180, S: 0-255, V: 0-255
        const lower = [
            Math.max(0, h - tol),
            Math.max(0, s - tol * 2),
            Math.max(0, v - tol * 2)
        ];
        const upper = [
            Math.min(180, h + tol),
            Math.min(255, s + tol * 2),
            Math.min(255, v + tol * 2)
        ];

        this.lowerText.textContent = `Lower: ${lower.join(', ')}`;
        this.upperText.textContent = `Upper: ${upper.join(', ')}`;
        
        color.lower = lower;
        color.upper = upper;

        // Trigger preview if enabled
        if (this.appState.showColorHighlight) {
            this.generateHighlightMask();
        }
    }

    saveCurrentColor() {
        if (!this.currentColor) return;

        const nameInput = document.getElementById('color-name-input');
        this.currentColor.name = nameInput.value || 'unnamed_color';
        
        if (this.selectedColorIndex !== -1) {
            // Update existing
            this.appState.colors[this.selectedColorIndex] = {...this.currentColor};
        } else {
            // Add new
            this.appState.colors.push({...this.currentColor});
        }
        
        this.onUpdate();
        
        // Hide panel
        this.panel.style.display = 'none';
        this.currentColor = null;
        this.selectedColorIndex = -1;
    }

    cancelPicker() {
        this.panel.style.display = 'none';
        this.currentColor = null;
        this.selectedColorIndex = -1;
        this.mask = null;
    }

    // Helper: RGB to OpenCV HSV
    rgbToHsv(r, g, b) {
        r /= 255; g /= 255; b /= 255;
        const max = Math.max(r, g, b), min = Math.min(r, g, b);
        let h, s, v = max;
        const d = max - min;
        s = max === 0 ? 0 : d / max;

        if (max === min) {
            h = 0;
        } else {
            switch (max) {
                case r: h = (g - b) / d + (g < b ? 6 : 0); break;
                case g: h = (b - r) / d + 2; break;
                case b: h = (r - g) / d + 4; break;
            }
            h /= 6;
        }

        return [
            Math.round(h * 180),
            Math.round(s * 255),
            Math.round(v * 255)
        ];
    }

    generateHighlightMask() {
        if (!this.currentColor || !this.imageCanvas.image) {
            this.mask = null;
            this.imageCanvas.draw();
            return;
        }

        const img = this.imageCanvas.image;
        const canvas = document.createElement('canvas');
        // Use a smaller scale for performance if needed, but requirements imply mask on full image
        // To keep it fast, we can sample or use a smaller canvas
        const scale = img.width > 800 ? 800 / img.width : 1;
        canvas.width = Math.round(img.width * scale);
        canvas.height = Math.round(img.height * scale);
        
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = imageData.data;
        
        const lower = this.currentColor.lower;
        const upper = this.currentColor.upper;

        for (let i = 0; i < data.length; i += 4) {
            const r = data[i];
            const g = data[i + 1];
            const b = data[i + 2];
            
            const [h, s, v] = this.rgbToHsv(r, g, b);
            
            // Check if within bounds
            const inRange = (h >= lower[0] && h <= upper[0]) &&
                            (s >= lower[1] && s <= upper[1]) &&
                            (v >= lower[2] && v <= upper[2]);
            
            if (inRange) {
                // Highlight: Yellowish/Cyan transparent overlay
                data[i] = 0;
                data[i + 1] = 255;
                data[i + 2] = 255;
                data[i + 3] = 150; // Alpha
            } else {
                data[i + 3] = 0; // Transparent
            }
        }
        
        ctx.putImageData(imageData, 0, 0);
        this.mask = canvas;
        this.imageCanvas.draw();
    }

    // This will be called by ImageCanvas.onDraw
    render(ctx) {
        if (this.appState.showColorHighlight && this.mask) {
            ctx.drawImage(this.mask, 0, 0, this.canvas.width, this.canvas.height);
        }
    }
}
