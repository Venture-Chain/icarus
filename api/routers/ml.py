from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class TrainRequest(BaseModel):
    model_name: str
    features: list[str] = []
    target: str = ""
    parameters: dict = {}


@router.post("/train")
async def train_model(request: TrainRequest):
    """Trigger ML model training (CUDA)."""
    return {"status": "queued", "model": request.model_name}


@router.post("/predict")
async def predict(model_name: str = ""):
    """Run inference with a trained model."""
    return {"model": model_name, "predictions": []}


@router.get("/experiments")
async def list_experiments():
    """List ML training experiments."""
    return {"experiments": []}
