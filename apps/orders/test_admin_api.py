import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Color, Product
from apps.orders.models import Customer, Order, OrderItem, OrderItemColor
from apps.payments.models import Payment
from apps.pickups.models import PickupLocation

ADMIN = "/api/admin/"


def png():
    buf = io.BytesIO()
    Image.new("RGB", (2, 2)).save(buf, "PNG")
    return SimpleUploadedFile("r.png", buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT="/tmp/test_media")
class AdminApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("admin", "a@a.com", "pw")
        cls.loc = PickupLocation.objects.create(name="Bole", area="Addis")
        cls.cust = Customer.objects.create(full_name="Sara", phone="0911")
        cls.cust2 = Customer.objects.create(full_name="Liya", phone="0922")

    def make_order(self, number="BR-1", status=Order.Status.PAYMENT_REVIEW, customer=None):
        o = Order.objects.create(
            order_number=number, customer=customer or self.cust, pickup_location=self.loc,
            status=status, total_amount="100.00", deposit_percent=50, deposit_amount="50.00",
        )
        return o

    def make_payment(self, order, status=Payment.Status.PENDING, ref="T1"):
        return Payment.objects.create(
            order=order, payment_type="deposit", method="telebirr", amount="50.00",
            transaction_ref=ref, screenshot=png(), status=status,
        )

    def login(self):
        self.client.force_authenticate(self.admin)

    # ---- auth
    def test_401_without_token_everywhere(self):
        o = self.make_order()
        p = self.make_payment(o)
        for method, url in [
            ("get", "orders/"), ("get", f"orders/{o.id}/"), ("patch", f"orders/{o.id}/status/"),
            ("get", "payments/"), ("post", f"payments/{p.id}/approve/"),
            ("post", f"payments/{p.id}/reject/"), ("get", "customers/"),
            ("get", f"customers/{self.cust.id}/"), ("patch", f"customers/{self.cust.id}/"),
        ]:
            r = getattr(self.client, method)(ADMIN + url)
            self.assertEqual(r.status_code, 401, (method, url))

    # ---- orders
    def test_order_list_filter_search_order(self):
        self.login()
        a = self.make_order("BR-A")
        b = self.make_order("BR-B", Order.Status.READY, self.cust2)
        r = self.client.get(ADMIN + "orders/")
        self.assertEqual([x["id"] for x in r.data["results"]], [b.id, a.id])  # newest first
        self.assertIn("count", r.data)
        self.assertEqual(self.client.get(ADMIN + "orders/?status=ready").data["count"], 1)
        self.assertEqual(self.client.get(ADMIN + "orders/?status=nope").status_code, 400)
        self.assertEqual(self.client.get(ADMIN + "orders/?search=0922").data["count"], 1)
        self.assertEqual(self.client.get(ADMIN + "orders/?search=BR-A").data["count"], 1)

    def test_order_list_no_n_plus_one(self):
        self.login()
        for i in range(5):
            self.make_order(f"BR-{i}")
        with self.assertNumQueries(2):  # count + one page query, regardless of row count
            self.client.get(ADMIN + "orders/")

    def test_order_detail_has_items_colors_and_receipt_url(self):
        self.login()
        o = self.make_order()
        self.make_payment(o)
        cat = Category.objects.create(name="c", slug="c")
        prod = Product.objects.create(category=cat, name="P", slug="p", price="100")
        item = OrderItem.objects.create(
            order=o, product=prod, product_name="P", unit_price="100", quantity=1,
            color_mode="custom",
        )
        OrderItemColor.objects.create(order_item=item, position=1, color=Color.objects.create(name="Red"))
        r = self.client.get(ADMIN + f"orders/{o.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["items"][0]["colors"][0]["position"], 1)
        self.assertTrue(r.data["payments"][0]["receipt"].startswith("http://testserver/"))
        self.assertEqual(self.client.get(ADMIN + "orders/99999/").status_code, 404)

    # ---- status
    def test_status_valid_and_invalid_transition(self):
        self.login()
        o = self.make_order(status=Order.Status.APPROVED)
        url = ADMIN + f"orders/{o.id}/status/"
        r = self.client.patch(url, {"status": "in_production"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "in_production")
        r = self.client.patch(url, {"status": "approved"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.patch(url, {"status": "bogus"}, format="json").status_code, 400)

    def test_status_blocks_review_shortcuts(self):
        self.login()
        o = self.make_order()
        url = ADMIN + f"orders/{o.id}/status/"
        for s in ("approved", "pending_payment"):
            r = self.client.patch(url, {"status": s}, format="json")
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data["detail"], "Use the payment approve/reject endpoints.")
        o.refresh_from_db()
        self.assertEqual(o.status, "payment_review")

    def test_status_repairs_review_when_payment_already_approved(self):
        self.login()
        o = self.make_order()
        self.make_payment(o, status=Payment.Status.APPROVED)
        r = self.client.patch(
            ADMIN + f"orders/{o.id}/status/", {"status": "approved"}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "approved")

    def test_status_repair_requires_no_pending_payment(self):
        self.login()
        o = self.make_order()
        self.make_payment(o, status=Payment.Status.APPROVED, ref="A")
        self.make_payment(o, status=Payment.Status.PENDING, ref="B")
        r = self.client.patch(
            ADMIN + f"orders/{o.id}/status/", {"status": "approved"}, format="json"
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["detail"], "Use the payment approve/reject endpoints.")

    def test_status_repair_requires_an_approved_payment(self):
        self.login()
        o = self.make_order()
        self.make_payment(o, status=Payment.Status.REJECTED)
        r = self.client.patch(
            ADMIN + f"orders/{o.id}/status/", {"status": "approved"}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_cancel_from_review_rejects_pending_payments(self):
        self.login()
        o = self.make_order()
        p = self.make_payment(o)
        r = self.client.patch(ADMIN + f"orders/{o.id}/status/", {"status": "cancelled"}, format="json")
        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.status, "rejected")
        self.assertIsNotNone(p.verified_at)

    # ---- payments
    def test_payment_list_filter_and_ordering(self):
        self.login()
        o1, o2 = self.make_order("BR-1"), self.make_order("BR-2", customer=self.cust2)
        p1, p2 = self.make_payment(o1, ref="A"), self.make_payment(o2, ref="B")
        pending = self.client.get(ADMIN + "payments/?status=pending").data["results"]
        self.assertEqual([x["id"] for x in pending], [p1.id, p2.id])  # oldest first
        allp = self.client.get(ADMIN + "payments/").data["results"]
        self.assertEqual([x["id"] for x in allp], [p2.id, p1.id])  # newest first
        self.assertEqual(pending[0]["customer_name"], "Sara")
        self.assertEqual(pending[0]["order_number"], "BR-1")
        self.assertTrue(pending[0]["receipt"].startswith("http"))
        self.assertEqual(self.client.get(ADMIN + "payments/?search=B").data["count"] >= 1, True)
        self.assertEqual(self.client.get(ADMIN + "payments/?status=x").status_code, 400)

    def test_approve_then_double_approve_409(self):
        self.login()
        o = self.make_order()
        p = self.make_payment(o)
        r = self.client.post(ADMIN + f"payments/{p.id}/approve/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["order_status"], "approved")
        self.assertEqual(r.data["status"], "approved")
        self.assertEqual(self.client.post(ADMIN + f"payments/{p.id}/approve/").status_code, 409)
        self.assertEqual(self.client.post(ADMIN + f"payments/{p.id}/reject/").status_code, 409)

    def test_reject_then_new_receipt_then_approve(self):
        self.login()
        o = self.make_order()
        p = self.make_payment(o)
        r = self.client.post(ADMIN + f"payments/{p.id}/reject/")
        self.assertEqual((r.status_code, r.data["order_status"]), (200, "pending_payment"))
        self.assertEqual(self.client.post(ADMIN + f"payments/{p.id}/reject/").status_code, 409)
        # customer uploads again through the public endpoint
        self.client.force_authenticate(None)
        up = self.client.post(
            f"/api/orders/{o.order_number}/payments/",
            {"method": "telebirr", "transaction_ref": "T2", "receipt": png()}, format="multipart",
        )
        self.assertEqual(up.status_code, 201, up.content)
        self.login()
        p2 = Payment.objects.get(transaction_ref="T2")
        self.assertEqual(self.client.post(ADMIN + f"payments/{p2.id}/approve/").status_code, 200)

    def test_full_happy_path_to_picked_up(self):
        self.login()
        o = self.make_order()
        p = self.make_payment(o)
        self.client.post(ADMIN + f"payments/{p.id}/approve/")
        for s in ("in_production", "ready", "picked_up"):
            r = self.client.patch(ADMIN + f"orders/{o.id}/status/", {"status": s}, format="json")
            self.assertEqual(r.status_code, 200)
        r = self.client.patch(ADMIN + f"orders/{o.id}/status/", {"status": "ready"}, format="json")
        self.assertEqual(r.status_code, 400)

    # ---- customers
    def test_customer_list_detail_patch(self):
        self.login()
        self.make_order("BR-1"); self.make_order("BR-2")
        lst = self.client.get(ADMIN + "customers/").data["results"]
        self.assertEqual(lst[0]["id"], self.cust2.id)  # newest first
        sara = next(c for c in lst if c["id"] == self.cust.id)
        self.assertEqual(sara["order_count"], 2)
        self.assertEqual(self.client.get(ADMIN + "customers/?search=Liya").data["count"], 1)
        d = self.client.get(ADMIN + f"customers/{self.cust.id}/").data
        self.assertEqual(len(d["orders"]), 2)
        url = ADMIN + f"customers/{self.cust.id}/"
        r = self.client.patch(url, {"full_name": "Sara T", "phone": "999", "email": "s@x.com"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.cust.refresh_from_db()
        self.assertEqual((self.cust.full_name, self.cust.phone), ("Sara T", "0911"))  # phone ignored
        self.assertEqual(self.client.delete(url).status_code, 405)
        self.assertEqual(self.client.put(url, {}, format="json").status_code, 405)
