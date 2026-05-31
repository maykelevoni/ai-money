from fastapi import FastAPI

app = FastAPI(title="ai-money engine", docs_url=None, redoc_url=None)


@app.get("/health")
def health():
    return {"status": "ok"}
