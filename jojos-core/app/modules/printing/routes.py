from fastapi import APIRouter

from app.modules.printing.service import create_kitchen_label_job, list_print_jobs_for_order, require_order_exists

router = APIRouter()


@router.post('/api/printing/orders/{order_id}/label')
def print_order_label(order_id: str):
    require_order_exists(order_id)
    return create_kitchen_label_job(order_id)


@router.get('/api/printing/orders/{order_id}/jobs')
def get_order_print_jobs(order_id: str):
    require_order_exists(order_id)
    return {'items': list_print_jobs_for_order(order_id)}
