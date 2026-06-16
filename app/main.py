from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import router_v2

load_dotenv()

app = FastAPI(
    root_path= "/imagegen",
    title= "KB Image Generation APIs"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router_v2)

@app.get("/")
def read_root():
    return {"This is": "Image Generation Application"}