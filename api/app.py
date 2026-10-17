from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router as api_v1_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Hackathon Ingestion Platform API",
        description="Unified REST API for discovering and querying hackathons from Devpost, Devfolio, and Unstop.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Enable CORS for public web frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_v1_router)

    @app.get("/", tags=["Root"])
    def root():
        return {
            "name": "Hackathon Ingestion Platform API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/v1/health",
            "hackathons": "/api/v1/hackathons",
        }

    return app


app = create_app()
