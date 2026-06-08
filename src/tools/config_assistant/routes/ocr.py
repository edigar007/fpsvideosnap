import os

from flask import jsonify, request
from PIL import Image

from src.tools.config_assistant.ocr_service import OCRUnavailableError, get_ocr_service
from src.utils.logger import get_logger

logger = get_logger("config_assistant.routes.ocr")


def _attach_relative_boxes(image_path: str, roi, results: list) -> None:
    if not roi or not results:
        return

    with Image.open(image_path) as img:
        img_w, img_h = img.size

    rx, ry, rw, rh = roi
    roi_px = [rx * img_w, ry * img_h, rw * img_w, rh * img_h]

    for res in results:
        bbox = res.get("bbox")
        if not bbox or not isinstance(bbox, list) or len(bbox) < 4:
            continue

        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        c_min_x = max(roi_px[0], min(roi_px[0] + roi_px[2], min_x))
        c_max_x = max(roi_px[0], min(roi_px[0] + roi_px[2], max_x))
        c_min_y = max(roi_px[1], min(roi_px[1] + roi_px[3], min_y))
        c_max_y = max(roi_px[1], min(roi_px[1] + roi_px[3], max_y))

        if roi_px[2] > 0 and roi_px[3] > 0:
            box_x = (c_min_x - roi_px[0]) / roi_px[2]
            box_y = (c_min_y - roi_px[1]) / roi_px[3]
            box_w = (c_max_x - c_min_x) / roi_px[2]
            box_h = (c_max_y - c_min_y) / roi_px[3]
            res["box"] = [float(box_x), float(box_y), float(box_w), float(box_h)]


def register_routes(bp) -> None:
    @bp.route("/ocr/detect", methods=["POST"])
    def ocr_detect():
        data = request.json
        image_path = data.get("image_path")
        roi = data.get("roi")

        logger.info(f"OCR API called with image_path={image_path}, roi={roi}")

        if not image_path:
            logger.error("OCR API: image_path is missing")
            return jsonify({"error": "image_path is required"}), 400

        if not os.path.exists(image_path):
            logger.error(f"OCR API: image file not found: {image_path}")
            return jsonify({"error": f"Image file not found: {image_path}"}), 404

        try:
            ocr_service = get_ocr_service()
            results = ocr_service.detect(image_path, roi)

            try:
                _attach_relative_boxes(image_path, roi, results)
            except Exception as exc:
                logger.error(f"Error calculating relative boxes for OCR: {exc}")

            logger.info(f"OCR API returning {len(results)} results")
            return jsonify({"results": results})
        except OCRUnavailableError as exc:
            logger.warning(f"OCR unavailable: {exc}")
            return (
                jsonify(
                    {
                        "error": "OCR unavailable",
                        "detail": str(exc),
                        "help": "Install .venv_paddle environment or set FPSVSNAP_CONFIG_OCR_DEVICE=disabled",
                    }
                ),
                503,
            )
        except Exception as exc:
            logger.error(f"OCR API error: {exc}", exc_info=True)
            return jsonify({"error": str(exc)}), 500

