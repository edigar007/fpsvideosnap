/**
 * Canvas State Management
 * Handles zooming, panning, and coordinate transformations.
 */
class CanvasState {
    constructor() {
        this.scale = 1.0;
        this.offsetX = 0;
        this.offsetY = 0;
        this.dragging = false;
        this.lastMouseX = 0;
        this.lastMouseY = 0;
        
        this.roi = null; // Current selected ROI: [x, y, w, h] in relative coords (0-1)
        this.subRoi = null; // Sub-ROI for templates (relative to ROI)
        this.mode = 'ROI'; // ROI, COLOR, TEMPLATE, OCR
        
        this.image = null;
        this.tempHighlights = []; // For OCR matches etc. [ [x,y,w,h], ... ]
        this.colorMask = null; // For color preview
        this.canvas = document.getElementById('main-canvas');
        this.ctx = this.canvas.getContext('2d');
        
        this.init();
    }

    init() {
        // Zoom events
        document.getElementById('zoom-in').addEventListener('click', () => this.adjustZoom(0.1));
        document.getElementById('zoom-out').addEventListener('click', () => this.adjustZoom(-0.1));
        document.getElementById('zoom-reset').addEventListener('click', () => this.resetView());
        
        // Tab changes affect mode
        document.addEventListener('tabChanged', (e) => {
            const tabId = e.detail.tabId;
            switch(tabId) {
                case 'roi': this.mode = 'ROI'; break;
                case 'ocr': this.mode = 'OCR'; break;
                case 'templates': this.mode = 'TEMPLATE'; break;
                case 'colors': this.mode = 'COLOR'; break;
            }
            // Reset state if needed
            this.subRoi = null;
            this.tempHighlights = [];
            this.colorMask = null;
            this.render();
        });

        // Mouse events for drawing/panning
        this.canvas.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        document.addEventListener('mouseup', (e) => this.handleMouseUp(e));
        
        // Color sampling click
        this.canvas.addEventListener('click', (e) => this.handleClick(e));

        window.addEventListener('resize', () => this.resetView());
    }

    resetView() {
        if (!this.image) return;
        
        const container = document.getElementById('canvas-viewport');
        if (!container) return;
        
        // 设置 canvas 尺寸为图片实际尺寸
        this.canvas.width = this.image.width;
        this.canvas.height = this.image.height;
        
        // 计算自适应缩放比例，确保图片完全可见
        const padding = 40;
        const availableW = container.clientWidth - padding;
        const availableH = container.clientHeight - padding;
        
        const scaleW = availableW / this.image.width;
        const scaleH = availableH / this.image.height;
        
        // 移除 1.0 的限制，允许小图片放大显示
        this.scale = Math.min(scaleW, scaleH);
        
        // 设置最小缩放为 0.1，最大缩放为 3.0
        this.scale = Math.max(0.1, Math.min(3.0, this.scale));
        
        this.updateZoomDisplay();
        this.render();
    }

    isPosInROI(relX, relY) {
        if (!this.roi) return false;
        const [rx, ry, rw, rh] = this.roi;
        return relX >= rx && relX <= rx + rw && relY >= ry && relY <= ry + rh;
    }

    getRelToROI(relX, relY) {
        if (!this.roi) return { x: 0, y: 0 };
        const [rx, ry, rw, rh] = this.roi;
        return {
            x: (relX - rx) / rw,
            y: (relY - ry) / rh
        };
    }

handleMouseDown(e) {
        if (!this.image) return;
        const pos = this.clientToCanvas(e.clientX, e.clientY);
        const relPos = { x: pos.x / this.canvas.width, y: pos.y / this.canvas.height };

        if (this.mode === 'ROI') {
            this.dragging = true;
            this.startPos = relPos;  // Store as relative coordinates (0-1)
            this.roi = [relPos.x, relPos.y, 0, 0];
        } else if (this.mode === 'TEMPLATE' && this.roi) {
            if (this.isPosInROI(relPos.x, relPos.y)) {
                this.dragging = true;
                this.startPos = relPos;  // Store as relative coordinates (0-1)
                const inner = this.getRelToROI(relPos.x, relPos.y);
                this.subRoi = [inner.x, inner.y, 0, 0];
            }
        }
    }

handleMouseMove(e) {
        if (!this.image) return;
        const pos = this.clientToCanvas(e.clientX, e.clientY);
        const relPos = { x: pos.x / this.canvas.width, y: pos.y / this.canvas.height };

        if (this.dragging) {
            if (this.mode === 'ROI') {
                const x = Math.min(relPos.x, this.startPos.x);
                const y = Math.min(relPos.y, this.startPos.y);
                const w = Math.abs(relPos.x - this.startPos.x);
                const h = Math.abs(relPos.y - this.startPos.y);

                this.roi = [x, y, w, h];
                document.dispatchEvent(new CustomEvent('roiChanged', { detail: { roi: this.roi } }));
                this.render();
            } else if (this.mode === 'TEMPLATE' && this.roi) {
                const [rx, ry, rw, rh] = this.roi;
                // Clamp relPos to ROI boundaries
                const clampedX = Math.max(rx, Math.min(rx + rw, relPos.x));
                const clampedY = Math.max(ry, Math.min(ry + rh, relPos.y));

                const startInner = this.getRelToROI(this.startPos.x, this.startPos.y);
                const currentInner = this.getRelToROI(clampedX, clampedY);

                const x = Math.min(startInner.x, currentInner.x);
                const y = Math.min(startInner.y, currentInner.y);
                const w = Math.abs(currentInner.x - startInner.x);
                const h = Math.abs(currentInner.y - startInner.y);

                this.subRoi = [x, y, w, h];
                document.dispatchEvent(new CustomEvent('subRoiChanged', { detail: { subRoi: this.subRoi } }));
                this.render();
            }
        }
    }

    handleMouseUp() {
        if (this.dragging) {
            this.dragging = false;
            if (this.mode === 'ROI') {
                document.dispatchEvent(new CustomEvent('roiSelected', { detail: { roi: this.roi } }));
            } else if (this.mode === 'TEMPLATE') {
                document.dispatchEvent(new CustomEvent('subRoiSelected', { detail: { subRoi: this.subRoi } }));
            }
        }
    }

    handleClick(e) {
        if (!this.image) return;
        const pos = this.clientToCanvas(e.clientX, e.clientY);
        const relPos = { x: pos.x / this.canvas.width, y: pos.y / this.canvas.height };

        if (this.mode === 'COLOR' && this.roi) {
            if (this.isPosInROI(relPos.x, relPos.y)) {
                const inner = this.getRelToROI(relPos.x, relPos.y);
                document.dispatchEvent(new CustomEvent('colorSampled', { 
                    detail: { 
                        pos: pos,
                        inner: inner
                    } 
                }));
            }
        }
    }

    adjustZoom(delta) {
        this.scale = Math.max(0.1, Math.min(5.0, this.scale + delta));
        this.updateZoomDisplay();
    }

    updateZoomDisplay() {
        this.canvas.style.transformOrigin = 'top left';
        this.canvas.style.transform = `scale(${this.scale})`;
    }

/**
     * Convert client coordinates (mouse) to canvas pixel coordinates
     */
    clientToCanvas(clientX, clientY) {
        // getBoundingClientRect() handles transform, scroll, and positioning automatically
        const rect = this.canvas.getBoundingClientRect();

        // Calculate position relative to canvas (accounts for transform scale)
        const x = (clientX - rect.left) / this.scale;
        const y = (clientY - rect.top) / this.scale;

        return { x, y };
    }

    /**
     * Convert canvas pixels to relative coordinates (0-1)
     */
    pixelToRelative(px, py) {
        if (!this.image) return { x: 0, y: 0 };
        return {
            x: px / this.image.width,
            y: py / this.image.height
        };
    }

setImage(img) {
        this.image = img;
        // Reset ROI when image changes because old ROI coordinates
        // might not be meaningful on a different image
        this.roi = null;
        this.subRoi = null;
        this.tempHighlights = [];
        this.colorMask = null;
        this.resetView();
    }

    resetSelection() {
        this.subRoi = null;
        this.tempHighlights = [];
        this.colorMask = null;
        this.render();
        console.log('[CanvasState] Selection reset');
    }

    render() {
        if (!this.image) return;
        
        // Clear and draw image
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.ctx.drawImage(this.image, 0, 0);

        // Draw color mask if exists
        if (this.colorMask) {
            this.drawColorMask();
        }
        
        // Draw overlays based on mode and state
        this.drawOverlays();
    }

    drawColorMask() {
        if (!this.colorMask || !this.roi) return;
        const [rx, ry, rw, rh] = this.roi;
        const rpx = rx * this.canvas.width;
        const rpy = ry * this.canvas.height;
        const rpw = rw * this.canvas.width;
        const rph = rh * this.canvas.height;

        // colorMask is a binary image (0/255) of size ROI
        // We temp draw it on a hidden canvas and then draw it back with globalAlpha
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = this.colorMask.width;
        tempCanvas.height = this.colorMask.height;
        const tempCtx = tempCanvas.getContext('2d');
        
        tempCtx.putImageData(this.colorMask, 0, 0);
        
        this.ctx.save();
        this.ctx.globalAlpha = 0.6;
        this.ctx.drawImage(tempCanvas, rpx, rpy, rpw, rph);
        this.ctx.restore();
    }

    drawOverlays() {
        const isDark = true;
        
        // Draw ROI
        if (this.roi) {
            const [rx, ry, rw, rh] = this.roi;
            const px = rx * this.canvas.width;
            const py = ry * this.canvas.height;
            const pw = rw * this.canvas.width;
            const ph = rh * this.canvas.height;
            
            this.ctx.strokeStyle = '#1f6feb';
            this.ctx.lineWidth = 2 / this.scale;
            this.ctx.strokeRect(px, py, pw, ph);
            
            this.ctx.fillStyle = 'rgba(31, 111, 235, 0.1)';
            this.ctx.fillRect(px, py, pw, ph);

            // Draw ROI label
            this.ctx.fillStyle = '#1f6feb';
            this.ctx.font = `${12 / this.scale}px sans-serif`;
            this.ctx.fillText('Killfeed ROI', px, py - 5 / this.scale);

            // Draw Sub-ROI (Template)
            if (this.subRoi && this.mode === 'TEMPLATE') {
                const spx = px + this.subRoi[0] * pw;
                const spy = py + this.subRoi[1] * ph;
                const spw = this.subRoi[2] * pw;
                const sph = this.subRoi[3] * ph;

                this.ctx.strokeStyle = '#f85149'; // Red for sub-roi
                this.ctx.lineWidth = 1.5 / this.scale;
                this.ctx.strokeRect(spx, spy, spw, sph);
                this.ctx.fillStyle = 'rgba(248, 81, 73, 0.2)';
                this.ctx.fillRect(spx, spy, spw, sph);
                
                this.ctx.fillStyle = '#f85149';
                this.ctx.fillText('Template Area', spx, spy - 5 / this.scale);
            }
        }

        // Draw Temp Highlights (e.g., OCR matches)
        if (this.tempHighlights && this.tempHighlights.length > 0 && this.roi) {
            const [rx, ry, rw, rh] = this.roi;
            const rpx = rx * this.canvas.width;
            const rpy = ry * this.canvas.height;
            const rpw = rw * this.canvas.width;
            const rph = rh * this.canvas.height;

            this.ctx.strokeStyle = '#238636'; // Green for matches
            this.ctx.lineWidth = 1 / this.scale;
            
            this.tempHighlights.forEach(box => {
                // box is [x, y, w, h] relative to ROI (0-1)
                const bx = rpx + box[0] * rpw;
                const by = rpy + box[1] * rph;
                const bw = box[2] * rpw;
                const bh = box[3] * rph;
                this.ctx.strokeRect(bx, by, bw, bh);
                this.ctx.fillStyle = 'rgba(35, 134, 54, 0.2)';
                this.ctx.fillRect(bx, by, bw, bh);
            });
        }
    }
}

// Global instance
window.canvasState = new CanvasState();
