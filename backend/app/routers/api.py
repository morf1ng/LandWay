"""HTTP API прототипа. Все разделы читают и меняют одно хранилище."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.deps import get_token, require_user
from app.services import operations
from app.services import queries
from app.store import store

public_router = APIRouter()
router = APIRouter()
UPLOADS = Path(__file__).resolve().parents[2] / "uploads"


def _mutate(mutator):
    try:
        return store.update(mutator)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@public_router.get("/health")
def health():
    return {"ok": True, "storage": "postgresql", "database": True, "auth": True}


@router.get("/meta")
def meta():
    return queries.meta(store.read())


@router.get("/dashboard")
def dashboard():
    return queries.dashboard(store.read())


@router.get("/shipments")
def list_shipments():
    data = store.read()
    return [queries.view_shipment(data, shipment) for shipment in data["shipments"]]


@router.post("/shipments")
def create_shipment(payload: dict):
    holder: dict = {}

    def mutate(data):
        holder["shipment"] = operations.create_shipment(data, payload)

    _mutate(mutate)
    data = store.read()
    return queries.shipment_detail(data, holder["shipment"]["id"])


@router.get("/shipments/{shipment_id}")
def get_shipment(shipment_id: str):
    detail = queries.shipment_detail(store.read(), shipment_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Груз не найден")
    return detail


@router.patch("/shipments/{shipment_id}")
def patch_shipment(shipment_id: str, payload: dict):
    def mutate(data):
        operations.update_shipment(data, shipment_id, payload)

    _mutate(mutate)
    return queries.shipment_detail(store.read(), shipment_id)


@router.get("/map")
def map_view():
    return queries.map_payload(store.read())


@router.get("/analytics")
def analytics():
    return queries.analytics(store.read())


@router.post("/analytics/ai/{shipment_id}")
def ai_analysis(shipment_id: str):
    from app.services.openrouter import AIUnavailable, explain

    row = next((item for item in queries.analytics(store.read())["rows"] if item["id"] == shipment_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Груз не найден")
    try:
        return explain(row)
    except AIUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/analytics/recalculate")
def recalculate(payload: dict | None = None):
    from app.services.engine import recalculate as run

    def mutate(data):
        run(data)

    _mutate(mutate)
    return queries.analytics(store.read())


@router.get("/routes")
def routes_catalog():
    return queries.route_catalog(store.read())


@router.get("/routes/options/{shipment_id}")
def route_options(shipment_id: str):
    data = store.read()
    if not any(item["id"] == shipment_id for item in data["shipments"]):
        raise HTTPException(status_code=404, detail="Груз не найден")
    from app.services.routing import options_for_shipment

    return options_for_shipment(data, shipment_id)


@router.post("/routes/select")
def select_route(payload: dict):
    shipment_id = payload.get("shipmentId")
    template_id = payload.get("templateId")
    if not shipment_id or not template_id:
        raise HTTPException(status_code=400, detail="Нужны shipmentId и templateId")

    def mutate(data):
        operations.select_route(data, shipment_id, template_id)

    _mutate(mutate)
    return queries.shipment_detail(store.read(), shipment_id)


@router.get("/documents")
def list_documents():
    return store.read()["documents"]


@router.post("/documents")
async def upload_document(shipmentId: str = Form(...), type: str = Form(...), file: UploadFile = File(...)):
    content = await file.read()
    holder: dict = {}

    def mutate(data):
        holder["document"] = operations.save_upload(data, shipmentId, type, file.filename or "file", content, UPLOADS)

    _mutate(mutate)
    return holder["document"]


@router.patch("/documents/{document_id}")
def patch_document(document_id: str, payload: dict):
    holder: dict = {}

    def mutate(data):
        holder["document"] = operations.update_document_fields(data, document_id, payload)

    _mutate(mutate)
    return holder["document"]


@router.get("/documents/{document_id}/file")
def download_document(document_id: str):
    data = store.read()
    document = next((item for item in data["documents"] if item["id"] == document_id), None)
    if document is None or not document.get("file"):
        raise HTTPException(status_code=404, detail="Файл не найден")
    path = (UPLOADS / document["file"]["storedName"]).resolve()
    if not str(path).startswith(str(UPLOADS.resolve())) or not path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path, filename=document["file"].get("originalName") or path.name)


@router.post("/documents/check")
def check_documents(payload: dict):
    shipment_id = payload.get("shipmentId")
    if not shipment_id:
        raise HTTPException(status_code=400, detail="Выберите груз")
    holder: dict = {}

    def mutate(data):
        holder["result"] = operations.check_documents(data, shipment_id)

    _mutate(mutate)
    return holder["result"]


@router.post("/documents/preclear")
def preclear(payload: dict):
    shipment_id = payload.get("shipmentId")
    if not shipment_id:
        raise HTTPException(status_code=400, detail="Выберите груз")
    holder: dict = {}

    def mutate(data):
        holder["result"] = operations.preclear(data, shipment_id)

    _mutate(mutate)
    return holder["result"]


@router.get("/corridor/contract/{shipment_id}")
def corridor_contract_status(shipment_id: str):
    from app.services.corridor_contract import status

    try:
        return status(store.read(), shipment_id, UPLOADS)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/corridor/contract/{shipment_id}/execute")
def execute_corridor_contract(shipment_id: str, user: dict = Depends(require_user)):
    from app.services.corridor_contract import execute

    holder: dict = {}

    def mutate(data):
        holder["result"] = execute(data, shipment_id, UPLOADS, user.get("name") or user.get("username") or "Демо-логист")

    _mutate(mutate)
    return holder["result"]


@router.get("/journal")
def journal():
    return queries.journal(store.read())


@router.get("/ecology")
def ecology(shipmentId: str | None = None, routeId: str | None = None):
    return queries.ecology(store.read(), shipmentId, routeId)


@router.patch("/ecology/factors")
def patch_factors(payload: dict):
    holder: dict = {}

    def mutate(data):
        holder["factors"] = operations.update_factors(data, payload)

    _mutate(mutate)
    return holder["factors"]


@router.get("/notifications")
def notifications():
    return store.read()["notifications"]


@router.post("/notifications/{notification_id}/read")
def read_notification(notification_id: str):
    holder: dict = {}

    def mutate(data):
        holder["item"] = operations.mark_notification(data, notification_id, True)

    _mutate(mutate)
    return holder["item"]


@router.post("/notifications/read-all")
def read_all():
    def mutate(data):
        operations.mark_all_notifications(data)

    _mutate(mutate)
    return {"ok": True}


@router.get("/profile")
def profile(user: dict = Depends(require_user)):
    from app.services.auth import profile_payload

    data = store.read()
    prof = data.get("profile") or {}
    if prof.get("userId") == user["id"]:
        return {**prof, "username": user["username"], "roleEditable": user.get("username") != "logist"}
    return profile_payload(user)


@router.patch("/profile")
def patch_profile(payload: dict, user: dict = Depends(require_user)):
    holder: dict = {}

    def mutate(data):
        holder["profile"] = operations.update_profile(data, payload, user["id"])

    _mutate(mutate)
    return holder["profile"]


@router.get("/ports")
def ports():
    return queries.dashboard(store.read())["ports"]
