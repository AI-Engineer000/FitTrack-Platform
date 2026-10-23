from celery import shared_task

from dashboard.frame_processing import process_frame


@shared_task
def analyze_frame_task(frame_data, exercise, state):
    try:
        return process_frame(frame_data, exercise, state)
    except Exception as error:
        return {"error": str(error)}
