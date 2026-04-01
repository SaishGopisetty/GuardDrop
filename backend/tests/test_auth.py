import importlib
import os
import sys
import asyncio
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import delete
from starlette.websockets import WebSocketDisconnect

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEST_DB_PATH = (BACKEND_DIR / ".test_auth.db").resolve()
TEST_DB_PATH.unlink(missing_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["GUARDDROP_SECRET_KEY"] = "guarddrop-test-secret"

for module_name in ["database", "models", "auth", "main"]:
    sys.modules.pop(module_name, None)

database = importlib.import_module("database")
models = importlib.import_module("models")
auth = importlib.import_module("auth")
main = importlib.import_module("main")


async def _noop_simulation(*_args, **_kwargs):
    return None


REAL_SIMULATE_DELIVERY = main.simulate_delivery
main.simulate_delivery = _noop_simulation


class AuthIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app, raise_server_exceptions=False)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        database.engine.dispose()
        TEST_DB_PATH.unlink(missing_ok=True)

    def setUp(self):
        models.Base.metadata.create_all(bind=database.engine)
        session = database.SessionLocal()
        session.execute(delete(models.DeliveryEvent))
        session.execute(delete(models.Delivery))
        session.execute(delete(models.SecondaryContact))
        session.execute(delete(models.User))
        session.commit()
        session.close()

    def signup(self, *, label: str):
        unique = uuid.uuid4().hex[:8]
        payload = {
            "name": f"User {label}",
            "phone": f"+1555{unique[:7]}",
            "email": f"{label}-{unique}@example.com",
            "password": "pw123456",
        }
        response = self.client.post("/signup", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return payload, response.json()

    @staticmethod
    def auth_headers(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def test_signup_and_login_return_access_tokens(self):
        payload, signup_session = self.signup(label="alpha")
        self.assertEqual(signup_session["token_type"], "bearer")
        self.assertEqual(signup_session["user"]["email"], payload["email"])
        self.assertTrue(signup_session["access_token"])

        login_response = self.client.post(
            "/login",
            json={"email": payload["email"], "password": payload["password"]},
        )
        self.assertEqual(login_response.status_code, 200, login_response.text)

        login_session = login_response.json()
        self.assertEqual(login_session["user"]["id"], signup_session["user"]["id"])
        self.assertTrue(login_session["access_token"])

    def test_routes_require_bearer_token(self):
        self.assertEqual(self.client.get("/deliveries").status_code, 401)
        self.assertEqual(self.client.get("/contacts").status_code, 401)
        self.assertEqual(self.client.get("/users/me").status_code, 401)

    def test_user_cannot_read_or_mutate_another_users_resources(self):
        _, alice_session = self.signup(label="alice")
        _, bob_session = self.signup(label="bob")

        alice_headers = self.auth_headers(alice_session["access_token"])
        bob_headers = self.auth_headers(bob_session["access_token"])

        contact_response = self.client.post(
            "/contacts",
            headers=alice_headers,
            json={"name": "Neighbor", "phone": "+15550000000"},
        )
        self.assertEqual(contact_response.status_code, 200, contact_response.text)

        delivery_response = self.client.post(
            "/deliveries",
            headers=alice_headers,
            json={"tracking_id": "ALICE-001", "retailer": "Amazon"},
        )
        self.assertEqual(delivery_response.status_code, 200, delivery_response.text)

        alice_user_id = alice_session["user"]["id"]
        alice_delivery_id = delivery_response.json()["id"]

        self.assertEqual(self.client.get(f"/users/{alice_user_id}", headers=bob_headers).status_code, 403)
        self.assertEqual(self.client.get(f"/contacts/{alice_user_id}", headers=bob_headers).status_code, 403)
        self.assertEqual(self.client.get(f"/deliveries/{alice_user_id}", headers=bob_headers).status_code, 403)
        self.assertEqual(
            self.client.get(f"/deliveries/{alice_delivery_id}/events", headers=bob_headers).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(f"/deliveries/{alice_delivery_id}/pickup", headers=bob_headers).status_code,
            404,
        )

    def test_create_routes_bind_records_to_authenticated_user(self):
        _, alice_session = self.signup(label="alice")
        _, bob_session = self.signup(label="bob")

        alice_id = alice_session["user"]["id"]
        bob_id = bob_session["user"]["id"]
        bob_headers = self.auth_headers(bob_session["access_token"])

        forbidden_delivery = self.client.post(
            "/deliveries",
            headers=bob_headers,
            json={"user_id": alice_id, "tracking_id": "SPOOF-001", "retailer": "Target"},
        )
        self.assertEqual(forbidden_delivery.status_code, 403)

        forbidden_contact = self.client.post(
            "/contacts",
            headers=bob_headers,
            json={"user_id": alice_id, "name": "Spoofed", "phone": "+15551112222"},
        )
        self.assertEqual(forbidden_contact.status_code, 403)

        created_delivery = self.client.post(
            "/deliveries",
            headers=bob_headers,
            json={"tracking_id": "BOB-001", "retailer": "UPS"},
        )
        self.assertEqual(created_delivery.status_code, 200, created_delivery.text)
        self.assertEqual(created_delivery.json()["user_id"], bob_id)

        created_contact = self.client.post(
            "/contacts",
            headers=bob_headers,
            json={"name": "Friend", "phone": "+15553334444"},
        )
        self.assertEqual(created_contact.status_code, 200, created_contact.text)
        self.assertEqual(created_contact.json()["user_id"], bob_id)

    def test_websocket_requires_a_matching_authenticated_user(self):
        _, alice_session = self.signup(label="alice")
        _, bob_session = self.signup(label="bob")

        alice_id = alice_session["user"]["id"]
        bob_id = bob_session["user"]["id"]
        alice_token = alice_session["access_token"]

        with self.client.websocket_connect(f"/ws/{alice_id}?token={alice_token}"):
            pass

        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect(f"/ws/{bob_id}?token={alice_token}"):
                pass


class EscalationOutcomeTests(unittest.TestCase):
    @staticmethod
    async def no_sleep(*_args, **_kwargs):
        return None

    def setUp(self):
        models.Base.metadata.create_all(bind=database.engine)
        session = database.SessionLocal()
        session.execute(delete(models.DeliveryEvent))
        session.execute(delete(models.Delivery))
        session.execute(delete(models.SecondaryContact))
        session.execute(delete(models.User))
        session.commit()
        session.close()

    def create_user(self, label: str) -> models.User:
        unique = uuid.uuid4().hex[:8]
        session = database.SessionLocal()
        user = models.User(
            name=f"User {label}",
            phone=f"+1555{unique[:7]}",
            email=f"{label}-{unique}@example.com",
            password_hash="hash",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        session.close()
        return user

    def create_delivery(self, user_id: int, tracking_id: str) -> models.Delivery:
        session = database.SessionLocal()
        delivery = models.Delivery(user_id=user_id, tracking_id=tracking_id, retailer="Amazon")
        session.add(delivery)
        session.commit()
        session.refresh(delivery)
        session.expunge(delivery)
        session.close()
        return delivery

    def create_contact(self, user_id: int, accepted: bool) -> models.SecondaryContact:
        session = database.SessionLocal()
        contact = models.SecondaryContact(
            user_id=user_id,
            name="Neighbor",
            phone="+15550001111",
            accepted=accepted,
        )
        session.add(contact)
        session.commit()
        session.refresh(contact)
        session.expunge(contact)
        session.close()
        return contact

    def run_delivery_simulation(self, delivery_id: int, user_id: int):
        with patch("main.asyncio.sleep", new=self.no_sleep):
            asyncio.run(REAL_SIMULATE_DELIVERY(delivery_id, user_id, "Amazon"))

    def fetch_delivery_and_events(self, delivery_id: int):
        session = database.SessionLocal()
        delivery = session.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
        events = session.query(models.DeliveryEvent).filter(
            models.DeliveryEvent.delivery_id == delivery_id
        ).order_by(models.DeliveryEvent.id.asc()).all()
        session.expunge_all()
        session.close()
        return delivery, events

    def test_secondary_alert_is_skipped_without_accepted_contact(self):
        user = self.create_user("skip")
        delivery = self.create_delivery(user.id, "SKIP-001")
        self.create_contact(user.id, accepted=False)

        self.run_delivery_simulation(delivery.id, user.id)
        saved_delivery, events = self.fetch_delivery_and_events(delivery.id)

        self.assertEqual(saved_delivery.status, "delivered")
        self.assertIsNone(saved_delivery.secondary_alerted_at)
        self.assertEqual(events[-1].event_type, "secondary_alert_skipped")
        self.assertIn("No accepted secondary contact", events[-1].note)

    def test_secondary_alert_failure_keeps_delivery_in_delivered_state(self):
        user = self.create_user("failed")
        delivery = self.create_delivery(user.id, "FAIL-001")
        self.create_contact(user.id, accepted=True)

        with patch("main.send_secondary_alert", return_value=(False, "provider unavailable")):
            self.run_delivery_simulation(delivery.id, user.id)

        saved_delivery, events = self.fetch_delivery_and_events(delivery.id)

        self.assertEqual(saved_delivery.status, "delivered")
        self.assertIsNone(saved_delivery.secondary_alerted_at)
        self.assertEqual(events[-1].event_type, "secondary_alert_failed")
        self.assertIn("provider unavailable", events[-1].note)

    def test_secondary_alert_success_marks_delivery_as_escalating(self):
        user = self.create_user("success")
        delivery = self.create_delivery(user.id, "SUCCESS-001")
        self.create_contact(user.id, accepted=True)

        with patch("main.send_secondary_alert", return_value=(True, None)):
            self.run_delivery_simulation(delivery.id, user.id)

        saved_delivery, events = self.fetch_delivery_and_events(delivery.id)

        self.assertEqual(saved_delivery.status, "escalating")
        self.assertIsNotNone(saved_delivery.secondary_alerted_at)
        self.assertEqual(events[-1].event_type, "secondary_alerted")


if __name__ == "__main__":
    unittest.main()
