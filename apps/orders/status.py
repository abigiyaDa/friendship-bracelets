from .models import Order

Status = Order.Status

# current status -> statuses it may move to
ALLOWED_TRANSITIONS = {
    Status.PENDING_PAYMENT: {Status.PAYMENT_REVIEW, Status.CANCELLED},
    # APPROVED = payment accepted; PENDING_PAYMENT = payment rejected
    Status.PAYMENT_REVIEW: {Status.APPROVED, Status.PENDING_PAYMENT, Status.CANCELLED},
    Status.APPROVED: {Status.IN_PRODUCTION, Status.CANCELLED},
    Status.IN_PRODUCTION: {Status.READY},
    Status.READY: {Status.PICKED_UP},
    Status.PICKED_UP: set(),
    Status.CANCELLED: set(),
}


class InvalidStatusTransition(Exception):
    def __init__(self, current, new):
        self.current = current
        self.new = new
        super().__init__(f"Cannot change order status from '{current}' to '{new}'.")


def can_transition(current, new):
    return new in ALLOWED_TRANSITIONS.get(current, set())


def change_status(order, new_status):
    """The only place an order's status should be changed."""
    if not can_transition(order.status, new_status):
        raise InvalidStatusTransition(order.status, new_status)
    order.status = new_status
    order.save(update_fields=["status", "updated_at"])
    return order