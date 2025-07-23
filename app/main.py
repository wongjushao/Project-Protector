from fastapi import FastAPI
from app.routers import upload
from app.routers import process_router
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Project Protector API", version="0.1")

app.include_router(upload.router, prefix="/api")
app.include_router(process_router.router, prefix="/process")


app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
