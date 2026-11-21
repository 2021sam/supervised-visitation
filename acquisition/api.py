from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .core import extract_links, rank_links
from .test_runner import run

app = FastAPI(title="Data Acquisition Engine — Test Lab", version="0.1.0")

class DiscoveryInput(BaseModel):
    html: str
    base_url: str

class RankingInput(BaseModel):
    links: list[dict]

@app.post("/api/v1/discovery")
def discovery(data: DiscoveryInput):
    try:
        return {"links": extract_links(data.html, data.base_url)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

@app.post("/api/v1/ranking")
def ranking(data: RankingInput):
    return {"ranked_links": rank_links(data.links)}

@app.post("/api/v1/test-runs/{case_name}")
def test_run(case_name: str, mode: str = "replay"):
    if mode != "replay":
        raise HTTPException(400, "Live fetching is CLI-only in this first version")
    try:
        return run(case_name, mode=mode)
    except KeyError:
        raise HTTPException(404, "Unknown test case")
