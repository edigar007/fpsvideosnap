/**
 * ROI Management and Interaction for Config Assistant
 */
class ROIHandler {
    constructor(canvas, imageCanvas, onUpdate) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.imageCanvas = imageCanvas; // Instance of ImageCanvas
        this.onUpdate = onUpdate; // Callback when ROIs change
        this.enabled = true; // Toggle tool

        this.rois = [];
        this.selectedIndex = -1;
        this.isDrawing = false;
        this.isDragging = false;
        this.isResizing = false;
        this.resizeHandle = null; // 'tl', 'tr', 'bl', 'br'
        
        this.startPos = { x: 0, y: 0 };
        this.currentPos = { x: 0, y: 0 };
        this.dragOffset = { x: 0, y: 0 };

        this.handleSize = 8;
        this.minSize = 0.005; // Minimum relative size

        this.initEvents();
    }

    initEvents() {
        this.canvas.addEventListener('mousedown', this.handleMouseDown.bind(this));
        this.canvas.addEventListener('mousemove', this.handleMouseMove.bind(this));
        this.canvas.addEventListener('mouseup', this.handleMouseUp.bind(this));
        window.addEventListener('keydown', this.handleKeyDown.bind(this));
    }

    handleMouseDown(e) {
        if (!this.enabled || !this.imageCanvas.image) return;
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Check if clicked on a handle of the selected ROI
        if (this.selectedIndex !== -1) {
            const handle = this.getHandleAt(x, y, this.rois[this.selectedIndex]);
            if (handle) {
                this.isResizing = true;
                this.resizeHandle = handle;
                this.startPos = { x, y };
                return;
            }
        }

        // Check if clicked inside an ROI (to select/drag)
        const clickedIndex = this.getROIAt(x, y);
        if (clickedIndex !== -1) {
            this.selectedIndex = clickedIndex;
            this.isDragging = true;
            const roi = this.rois[this.selectedIndex];
            const canvasRect = this.roiToCanvas(roi);
            this.dragOffset = {
                x: x - canvasRect.x,
                y: y - canvasRect.y
            };
            this.onUpdate();
            this.imageCanvas.draw(); // Redraw with selection
            return;
        }

        // Otherwise, start drawing a new ROI
        this.selectedIndex = -1;
        this.isDrawing = true;
        this.startPos = { x, y };
        this.currentPos = { x, y };
        this.onUpdate();
    }

    handleMouseMove(e) {
        if (!this.enabled || !this.imageCanvas.image) return;
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        if (this.isDrawing) {
            this.currentPos = { x, y };
            this.imageCanvas.draw();
            this.drawPreview();
        } else if (this.isDragging && this.selectedIndex !== -1) {
            const roi = this.rois[this.selectedIndex];
            const canvasRect = this.roiToCanvas(roi);
            
            let newX = x - this.dragOffset.x;
            let newY = y - this.dragOffset.y;

            // Clamp to canvas
            newX = Math.max(0, Math.min(newX, this.canvas.width - canvasRect.w));
            newY = Math.max(0, Math.min(newY, this.canvas.height - canvasRect.h));

            const rel = this.canvasToRelative(newX, newY, canvasRect.w, canvasRect.h);
            roi.x = rel.x;
            roi.y = rel.y;
            
            this.imageCanvas.draw();
            this.onUpdate();
        } else if (this.isResizing && this.selectedIndex !== -1) {
            this.performResize(x, y);
            this.imageCanvas.draw();
            this.onUpdate();
        } else {
            // Update cursor
            this.updateCursor(x, y);
        }
    }

    handleMouseUp() {
        if (this.isDrawing) {
            const x1 = this.startPos.x;
            const y1 = this.startPos.y;
            const x2 = this.currentPos.x;
            const y2 = this.currentPos.y;

            const x = Math.min(x1, x2);
            const y = Math.min(y1, y2);
            const w = Math.abs(x1 - x2);
            const h = Math.abs(y1 - y2);

            if (w > 5 && h > 5) {
                const rel = this.canvasToRelative(x, y, w, h);
                this.addROI(`ROI ${this.rois.length + 1}`, rel.x, rel.y, rel.w, rel.h);
            }
        }
        this.isDrawing = false;
        this.isDragging = false;
        this.isResizing = false;
        this.resizeHandle = null;
        this.imageCanvas.draw();
    }

    handleKeyDown(e) {
        if (e.key === 'Delete' || e.key === 'Backspace') {
            // Don't delete if an input is focused
            if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;
            this.deleteSelected();
        }
    }

    addROI(name, x, y, w, h) {
        this.rois.push({ name, x, y, w, h });
        this.selectedIndex = this.rois.length - 1;
        this.onUpdate();
    }

    deleteSelected() {
        if (this.selectedIndex !== -1) {
            this.rois.splice(this.selectedIndex, 1);
            this.selectedIndex = -1;
            this.onUpdate();
            this.imageCanvas.draw();
        }
    }

    clearAll() {
        this.rois = [];
        this.selectedIndex = -1;
        this.onUpdate();
        this.imageCanvas.draw();
    }

    getROIAt(x, y) {
        for (let i = this.rois.length - 1; i >= 0; i--) {
            const rect = this.roiToCanvas(this.rois[i]);
            if (x >= rect.x && x <= rect.x + rect.w && y >= rect.y && y <= rect.y + rect.h) {
                return i;
            }
        }
        return -1;
    }

    getHandleAt(x, y, roi) {
        const rect = this.roiToCanvas(roi);
        const hs = this.handleSize;
        
        const handles = {
            tl: { x: rect.x, y: rect.y },
            tr: { x: rect.x + rect.w, y: rect.y },
            bl: { x: rect.x, y: rect.y + rect.h },
            br: { x: rect.x + rect.w, y: rect.y + rect.h }
        };

        for (const [key, pos] of Object.entries(handles)) {
            if (Math.abs(x - pos.x) <= hs && Math.abs(y - pos.y) <= hs) {
                return key;
            }
        }
        return null;
    }

    performResize(x, y) {
        const roi = this.rois[this.selectedIndex];
        const rect = this.roiToCanvas(roi);
        let x1 = rect.x;
        let y1 = rect.y;
        let x2 = rect.x + rect.w;
        let y2 = rect.y + rect.h;

        if (this.resizeHandle.includes('t')) y1 = Math.min(y, y2 - 5);
        if (this.resizeHandle.includes('b')) y2 = Math.max(y, y1 + 5);
        if (this.resizeHandle.includes('l')) x1 = Math.min(x, x2 - 5);
        if (this.resizeHandle.includes('r')) x2 = Math.max(x, x1 + 5);

        // Clamp to canvas
        x1 = Math.max(0, x1);
        y1 = Math.max(0, y1);
        x2 = Math.min(this.canvas.width, x2);
        y2 = Math.min(this.canvas.height, y2);

        const rel = this.canvasToRelative(x1, y1, x2 - x1, y2 - y1);
        roi.x = rel.x;
        roi.y = rel.y;
        roi.w = rel.w;
        roi.h = rel.h;
    }

    updateCursor(x, y) {
        if (this.selectedIndex !== -1) {
            const handle = this.getHandleAt(x, y, this.rois[this.selectedIndex]);
            if (handle) {
                this.canvas.style.cursor = (handle === 'tl' || handle === 'br') ? 'nwse-resize' : 'nesw-resize';
                return;
            }
        }
        
        if (this.getROIAt(x, y) !== -1) {
            this.canvas.style.cursor = 'move';
        } else {
            this.canvas.style.cursor = 'crosshair';
        }
    }

    render() {
        this.rois.forEach((roi, index) => {
            const rect = this.roiToCanvas(roi);
            const isSelected = index === this.selectedIndex;

            // Draw rect
            this.ctx.strokeStyle = isSelected ? '#00ff00' : '#ffff00';
            this.ctx.lineWidth = 2;
            this.ctx.fillStyle = isSelected ? 'rgba(0, 255, 0, 0.2)' : 'rgba(255, 255, 0, 0.1)';
            
            this.ctx.strokeRect(rect.x, rect.y, rect.w, rect.h);
            this.ctx.fillRect(rect.x, rect.y, rect.w, rect.h);

            // Draw label
            this.ctx.fillStyle = isSelected ? '#00ff00' : '#ffff00';
            this.ctx.font = '12px Arial';
            this.ctx.fillText(roi.name, rect.x, rect.y - 5);

            // Draw handles if selected
            if (isSelected) {
                this.drawHandles(rect);
            }
        });
    }

    drawHandles(rect) {
        const hs = this.handleSize;
        this.ctx.fillStyle = '#ffffff';
        this.ctx.strokeStyle = '#000000';
        this.ctx.lineWidth = 1;

        const positions = [
            { x: rect.x, y: rect.y },
            { x: rect.x + rect.w, y: rect.y },
            { x: rect.x, y: rect.y + rect.h },
            { x: rect.x + rect.w, y: rect.y + rect.h }
        ];

        positions.forEach(pos => {
            this.ctx.fillRect(pos.x - hs/2, pos.y - hs/2, hs, hs);
            this.ctx.strokeRect(pos.x - hs/2, pos.y - hs/2, hs, hs);
        });
    }

    drawPreview() {
        const x1 = this.startPos.x;
        const y1 = this.startPos.y;
        const x2 = this.currentPos.x;
        const y2 = this.currentPos.y;

        this.ctx.strokeStyle = '#ffffff';
        this.ctx.setLineDash([5, 5]);
        this.ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
        this.ctx.setLineDash([]);
    }

    // Converters
    canvasToRelative(x, y, w, h) {
        return {
            x: x / this.canvas.width,
            y: y / this.canvas.height,
            w: w / this.canvas.width,
            h: h / this.canvas.height
        };
    }

    roiToCanvas(roi) {
        return {
            x: roi.x * this.canvas.width,
            y: roi.y * this.canvas.height,
            w: roi.w * this.canvas.width,
            h: roi.h * this.canvas.height
        };
    }
}
