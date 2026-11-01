from celery import shared_task
import logging

from dashboard.frame_processing import process_frame


logger = logging.getLogger(__name__)


@shared_task
def analyze_frame_task(frame_data, exercise, state, athlete_height_cm=None):
    try:
        return process_frame(
            frame_data, exercise, state, athlete_height_cm)
    except Exception:
        logger.exception("Asynchronous frame analysis failed")
        return {"error": "Frame analysis failed"}
