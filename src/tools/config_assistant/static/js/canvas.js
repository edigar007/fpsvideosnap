/**
 * Canvas handling for Config Assistant
 */
class ImageCanvas {
    constructor(canvasId, containerId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.container = document.getElementById(containerId);
        this.image = null;
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;
        this.onDraw = null; // Callback for adding layers (like ROIs)
        
        window.addEventListener('resize', () => this.resize());
    }

    /**
     * Load image from file or URL
     */
    async loadImage(source) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => {
                this.image = img;
                this.resize();
                resolve(img);
            };
            img.onerror = reject;
            
            if (source instanceof File) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    img.src = e.target.result;
                };
                reader.readAsDataURL(source);
            } else {
                img.src = source;
            }
        });
    }

    /**
     * Resize canvas to fit container while maintaining aspect ratio
     */
    resize() {
        if (!this.image) return;

        const containerWidth = this.container.clientWidth;
        const containerHeight = this.container.clientHeight;
        
        const imgAspectRatio = this.image.width / this.image.height;
        const containerAspectRatio = containerWidth / containerHeight;

        let displayWidth, displayHeight;

        if (imgAspectRatio > containerAspectRatio) {
            // Image is wider than container relative to height
            displayWidth = containerWidth;
            displayHeight = containerWidth / imgAspectRatio;
        } else {
            // Image is taller than container relative to width
            displayHeight = containerHeight;
            displayWidth = containerHeight * imgAspectRatio;
        }

        // Apply scale
        this.scale = displayWidth / this.image.width;
        
        this.canvas.width = displayWidth;
        this.canvas.height = displayHeight;
        
        this.draw();
    }

    /**
     * Draw the image on canvas
     */
    draw() {
        if (!this.image) return;
        
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.ctx.drawImage(
            this.image, 
            0, 0, this.image.width, this.image.height,
            0, 0, this.canvas.width, this.canvas.height
        );

        if (this.onDraw) {
            this.onDraw(this.ctx);
        }
    }

    /**
     * Get real image coordinates from mouse coordinates
     */
    getRealCoords(canvasX, canvasY) {
        return {
            x: Math.round(canvasX / this.scale),
            y: Math.round(canvasY / this.scale)
        };
    }
}
