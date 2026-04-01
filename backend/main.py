import asyncio
from datetime import datetime
import os

import bcrypt
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

import auth
import database
import models

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="GuardDrop API")

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "GUARDDROP_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def serialize_user(user: models.User) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email}


def auth_response(user: models.User) -> dict:
    return {
        "access_token": auth.create_access_token(user.id),
        "token_type": "bearer",
        "user": serialize_user(user),
    }


def require_matching_user(requested_user_id: int, current_user: models.User) -> None:
    if requested_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def get_owned_delivery_or_404(
    delivery_id: int,
    current_user: models.User,
    db: Session,
) -> models.Delivery:
    delivery = db.query(models.Delivery).filter(
        models.Delivery.id == delivery_id,
        models.Delivery.user_id == current_user.id,
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return delivery


def get_owned_contact_or_404(
    contact_id: int,
    current_user: models.User,
    db: Session,
) -> models.SecondaryContact:
    contact = db.query(models.SecondaryContact).filter(
        models.SecondaryContact.id == contact_id,
        models.SecondaryContact.user_id == current_user.id,
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


def get_latest_delivery_event(delivery_id: int, db: Session) -> models.DeliveryEvent | None:
    return db.query(models.DeliveryEvent).filter(
        models.DeliveryEvent.delivery_id == delivery_id
    ).order_by(
        models.DeliveryEvent.timestamp.desc(),
        models.DeliveryEvent.id.desc(),
    ).first()


def serialize_delivery(delivery: models.Delivery, db: Session) -> dict:
    latest_event = get_latest_delivery_event(delivery.id, db)
    return {
        "id": delivery.id,
        "user_id": delivery.user_id,
        "tracking_id": delivery.tracking_id,
        "retailer": delivery.retailer,
        "status": delivery.status,
        "eta_sent_at": delivery.eta_sent_at,
        "delivered_at": delivery.delivered_at,
        "picked_up_at": delivery.picked_up_at,
        "secondary_alerted_at": delivery.secondary_alerted_at,
        "latest_event_type": latest_event.event_type if latest_event else None,
        "latest_event_note": latest_event.note if latest_event else None,
    }


def get_accepted_contact_for_user(user_id: int, db: Session) -> models.SecondaryContact | None:
    return db.query(models.SecondaryContact).filter(
        models.SecondaryContact.user_id == user_id,
        models.SecondaryContact.accepted.is_(True),
    ).order_by(models.SecondaryContact.id.asc()).first()


def send_secondary_alert(contact: models.SecondaryContact, delivery: models.Delivery) -> tuple[bool, str | None]:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")

    if not account_sid or not auth_token or not from_number:
        return False, "SMS alerts are not configured"

    try:
        from twilio.rest import Client

        client = Client(account_sid, auth_token)
        client.messages.create(
            body=(
                f"GuardDrop alert: {delivery.retailer} package {delivery.tracking_id} "
                "is still unattended. Please help secure it if you can."
            ),
            from_=from_number,
            to=contact.phone,
        )
        return True, None
    except Exception as exc:
        return False, str(exc)


class ConnectionManager:
    def __init__(self):
        self.connections: dict[int, list[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket):
        user_connections = self.connections.get(user_id, [])
        if not user_connections:
            return

        remaining_connections = [connection for connection in user_connections if connection is not websocket]
        if remaining_connections:
            self.connections[user_id] = remaining_connections
        else:
            self.connections.pop(user_id, None)

    async def send(self, user_id: int, data: dict):
        stale_connections = []
        for websocket in list(self.connections.get(user_id, [])):
            try:
                await websocket.send_json(data)
            except Exception:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            self.disconnect(user_id, websocket)


manager = ConnectionManager()


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    db = database.SessionLocal()
    try:
        try:
            current_user = auth.get_websocket_user(websocket, db)
        except HTTPException:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    finally:
        db.close()

    if current_user.id != user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)


async def simulate_delivery(delivery_id: int, user_id: int, retailer: str):
    await asyncio.sleep(10)
    db = database.SessionLocal()
    try:
        delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
        if not delivery or delivery.status != "pending":
            return
        delivery.status = "eta_sent"
        delivery.eta_sent_at = datetime.utcnow()
        db.add(models.DeliveryEvent(delivery_id=delivery_id, event_type="eta_sent"))
        db.commit()
    finally:
        db.close()

    await manager.send(
        user_id,
        {
            "type": "eta_sent",
            "delivery_id": delivery_id,
            "title": "Driver is nearby",
            "message": f"Your {retailer} driver is about 10 minutes away. Get ready!",
        },
    )

    await asyncio.sleep(10)
    db = database.SessionLocal()
    try:
        delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
        if not delivery or delivery.status != "eta_sent":
            return
        delivery.status = "delivered"
        delivery.delivered_at = datetime.utcnow()
        db.add(models.DeliveryEvent(delivery_id=delivery_id, event_type="delivered"))
        db.commit()
    finally:
        db.close()

    await manager.send(
        user_id,
        {
            "type": "delivered",
            "delivery_id": delivery_id,
            "title": "Package delivered!",
            "message": f"Your {retailer} package has been dropped off. Slide to confirm pickup.",
        },
    )

    await asyncio.sleep(20)
    db = database.SessionLocal()
    try:
        delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
        if not delivery or delivery.status != "delivered":
            return
        db.add(
            models.DeliveryEvent(
                delivery_id=delivery_id,
                event_type="escalation_1",
                note="First escalation - package unattended",
            )
        )
        db.commit()
    finally:
        db.close()

    await manager.send(
        user_id,
        {
            "type": "escalation_1",
            "delivery_id": delivery_id,
            "title": "Still waiting?",
            "message": f"Your {retailer} package is still sitting outside. Please pick it up soon.",
        },
    )

    await asyncio.sleep(20)
    db = database.SessionLocal()
    try:
        delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
        if not delivery or delivery.status != "delivered":
            return
        has_accepted_contact = get_accepted_contact_for_user(user_id, db) is not None
        db.add(
            models.DeliveryEvent(
                delivery_id=delivery_id,
                event_type="escalation_2",
                note=(
                    "Second escalation - urgent"
                    if has_accepted_contact
                    else "Second escalation - urgent, but no accepted contact is available"
                ),
            )
        )
        db.commit()
    finally:
        db.close()

    await manager.send(
        user_id,
        {
            "type": "escalation_2",
            "delivery_id": delivery_id,
            "title": "Urgent - package still outside!",
            "message": (
                f"Your {retailer} package has been unattended for a while. "
                + (
                    "We'll try to alert your trusted contact shortly."
                    if has_accepted_contact
                    else "No accepted trusted contact is on file yet, so automatic escalation is unavailable."
                )
            ),
        },
    )

    await asyncio.sleep(20)
    db = database.SessionLocal()
    try:
        delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
        if not delivery or delivery.status != "delivered":
            return
        contact = get_accepted_contact_for_user(user_id, db)

        if not contact:
            db.add(
                models.DeliveryEvent(
                    delivery_id=delivery_id,
                    event_type="secondary_alert_skipped",
                    note="No accepted secondary contact available",
                )
            )
            db.commit()
            event_payload = {
                "type": "secondary_alert_skipped",
                "delivery_id": delivery_id,
                "title": "No trusted contact to alert",
                "message": (
                    f"Your {retailer} package is still unattended, but no accepted trusted contact "
                    "is available for escalation."
                ),
            }
        else:
            alert_sent, error_message = send_secondary_alert(contact, delivery)
            if alert_sent:
                delivery.status = "escalating"
                delivery.secondary_alerted_at = datetime.utcnow()
                db.add(
                    models.DeliveryEvent(
                        delivery_id=delivery_id,
                        event_type="secondary_alerted",
                        note=f"Alert sent to {contact.name} at {contact.phone}",
                    )
                )
                db.commit()
                event_payload = {
                    "type": "secondary_alerted",
                    "delivery_id": delivery_id,
                    "title": "Secondary contact alerted",
                    "message": (
                        f"We alerted {contact.name} to help secure your {retailer} package."
                    ),
                }
            else:
                db.add(
                    models.DeliveryEvent(
                        delivery_id=delivery_id,
                        event_type="secondary_alert_failed",
                        note=f"Could not alert {contact.name}: {error_message}",
                    )
                )
                db.commit()
                event_payload = {
                    "type": "secondary_alert_failed",
                    "delivery_id": delivery_id,
                    "title": "Couldn't alert your contact",
                    "message": (
                        f"We tried to notify {contact.name}, but the alert failed. "
                        "Please check on the package yourself."
                    ),
                }
    finally:
        db.close()

    await manager.send(user_id, event_payload)


class SignupRequest(BaseModel):
    name: str
    phone: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class SecondaryContactCreate(BaseModel):
    user_id: int | None = None
    name: str
    phone: str


class DeliveryCreate(BaseModel):
    user_id: int | None = None
    tracking_id: str
    retailer: str


@app.post("/signup")
def signup(body: SignupRequest, db: Session = Depends(database.get_db)):
    if db.query(models.User).filter(models.User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = models.User(
        name=body.name,
        phone=body.phone,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return auth_response(new_user)


@app.post("/login")
def login(body: LoginRequest, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return auth_response(user)


@app.get("/users/me")
def get_current_profile(current_user: models.User = Depends(auth.get_current_user)):
    return serialize_user(current_user)


@app.get("/users/{user_id}")
def get_user(user_id: int, current_user: models.User = Depends(auth.get_current_user)):
    require_matching_user(user_id, current_user)
    return serialize_user(current_user)


@app.post("/contacts")
def add_contact(
    contact: SecondaryContactCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    if contact.user_id is not None and contact.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    new_contact = models.SecondaryContact(
        user_id=current_user.id,
        name=contact.name,
        phone=contact.phone,
    )
    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    return new_contact


@app.post("/contacts/{contact_id}/accept")
def accept_contact(
    contact_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    contact = get_owned_contact_or_404(contact_id, current_user, db)
    contact.accepted = True
    db.commit()
    return {"id": contact.id, "accepted": True}


@app.get("/contacts")
def get_contacts(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    return db.query(models.SecondaryContact).filter(
        models.SecondaryContact.user_id == current_user.id
    ).all()


@app.get("/contacts/{user_id}")
def get_contacts_for_user(
    user_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    require_matching_user(user_id, current_user)
    return db.query(models.SecondaryContact).filter(
        models.SecondaryContact.user_id == current_user.id
    ).all()


@app.post("/deliveries")
async def create_delivery(
    delivery: DeliveryCreate,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    if delivery.user_id is not None and delivery.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    new_delivery = models.Delivery(
        user_id=current_user.id,
        tracking_id=delivery.tracking_id,
        retailer=delivery.retailer,
    )
    db.add(new_delivery)
    db.commit()
    db.refresh(new_delivery)

    background_tasks.add_task(
        simulate_delivery,
        new_delivery.id,
        current_user.id,
        delivery.retailer,
    )
    return serialize_delivery(new_delivery, db)


@app.get("/deliveries")
def get_deliveries(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    deliveries = db.query(models.Delivery).filter(models.Delivery.user_id == current_user.id).all()
    return [serialize_delivery(delivery, db) for delivery in deliveries]


@app.get("/deliveries/{user_id}")
def get_deliveries_for_user(
    user_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    require_matching_user(user_id, current_user)
    deliveries = db.query(models.Delivery).filter(models.Delivery.user_id == current_user.id).all()
    return [serialize_delivery(delivery, db) for delivery in deliveries]


@app.post("/deliveries/{delivery_id}/pickup")
async def confirm_pickup(
    delivery_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    delivery = get_owned_delivery_or_404(delivery_id, current_user, db)
    delivery.status = "picked_up"
    delivery.picked_up_at = datetime.utcnow()
    db.add(models.DeliveryEvent(delivery_id=delivery_id, event_type="picked_up"))
    db.commit()

    await manager.send(
        current_user.id,
        {
            "type": "picked_up",
            "delivery_id": delivery_id,
            "title": "Package secured!",
            "message": f"Your {delivery.retailer} package has been picked up. Delivery complete.",
        },
    )

    return {"message": "Pickup confirmed", "picked_up_at": delivery.picked_up_at}


@app.get("/deliveries/{delivery_id}/events")
def get_events(
    delivery_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    delivery = get_owned_delivery_or_404(delivery_id, current_user, db)
    return db.query(models.DeliveryEvent).filter(
        models.DeliveryEvent.delivery_id == delivery.id
    ).order_by(models.DeliveryEvent.timestamp).all()
