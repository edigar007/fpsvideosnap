# Learnings: bug-xxx (ROI Click Offset Fix)

## 2026-01-21 Session: ses_41f945dd6ffeL4B6lwm1OuBZ16

### Root Cause Identified

The `clientToCanvas()` function in `canvas-state.js` was incorrectly using `/ this.scale` to convert mouse coordinates to canvas pixel coordinates.

**Why this was wrong:**
- `getBoundingClientRect()` returns the **CSS-transformed** (visually scaled) dimensions
- When CSS `transform: scale(X)` is applied, `rect.width = canvas.width * X` (approximately)
- Dividing by `this.scale` again was **double-compensating** for the scale
- This caused proportional offset: the further right/down you click, the larger the offset

### Fix Applied

Changed from:
```javascript
const x = (clientX - rect.left) / this.scale;
const y = (clientY - rect.top) / this.scale;
```

To:
```javascript
const scaleX = this.canvas.width / rect.width;
const scaleY = this.canvas.height / rect.height;
let x = (clientX - rect.left) * scaleX;
let y = (clientY - rect.top) * scaleY;
// + clamp to bounds
```

### Why DOMRect-based approach is better

1. **Self-correcting**: Uses actual rendered size, not theoretical scale
2. **Handles CSS constraints**: Works even if `max-width: 100%` or other CSS affects rendering
3. **DPR-agnostic**: Works correctly regardless of device pixel ratio
4. **Browser zoom safe**: Works when user zooms browser (Ctrl+/-)

### Conventions Discovered

- Canvas uses `transform: scale()` for zooming, applied via `updateZoomDisplay()`
- Canvas intrinsic size = image natural size (set in `resetView()`)
- ROI coordinates are always normalized 0-1 before storage
- All mouse modes (ROI/TEMPLATE/COLOR) use the same `clientToCanvas()` function

### Files Modified

- `src/tools/config_assistant/static/js/canvas-state.js:199-222` - clientToCanvas() function

### Verification Results

**Mathematical Proof:**
```
Scenario: canvas 1920x1080, JS thinks scale=1.0, but CSS renders at 800x450

OLD CODE (using js_scale=1.0):
  Click at center (500, 225)
  Calculated: (400, 225)
  Expected: (960, 540)
  RESULT: OFF BY 560px horizontally!

NEW CODE (using actual rect ratio):
  scaleX = 1920/800 = 2.4
  Click at center (500, 225)  
  Calculated: (960, 540)
  Expected: (960, 540)
  RESULT: CORRECT!
```

**Server Verification:**
- Created `.venv` and installed dependencies (flask, pyyaml, pillow, rich, opencv-python, numpy)
- Started server: `.venv/Scripts/python.exe main.py config-assistant --port 8080`
- Verified fixed code is being served via `curl http://localhost:8080/static/js/canvas-state.js`
- Confirmed the new `clientToCanvas()` implementation with DOMRect ratio calculation is active
