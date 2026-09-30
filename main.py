import os
import sys
import shutil
import tempfile

from requests import Session
from services.aggregation import get_rollup_by_level

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
from fastapi import Depends, FastAPI, HTTPException, UploadFile

from services.parser import parse_pdf
import database
import models

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

@app.post("/api/data/evidence/parse")
async def extract_and_save_bill(
    project_id: int,
    file:UploadFile,
    db: Session = Depends(database.get_db),
    ):
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        shutil.copyfileobj(file.file, temp_file)
        temp_path = temp_file.name
        
    extracted = parse_pdf(temp_path)
    
    # Storing the extracted data
    db_entry = models.ESGMetricEntry(
        project_id=project_id,
        metric_type=extracted["metric_type"],
        raw_value=extracted["raw_value"],
        unit=extracted["unit"],
        billing_period=extracted["billing_period"],
    )
    
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    
    return {
        "message": "Bill exracted and saved successfully.",
        "record": db_entry,
    }
    
@app.get("/api/reports/aggregate/{level}/{entity_id}")
def aggregate_metrics(
    level: str, entity_id: int, db: Session = Depends(database.get_db)
):
    # get aggrigated ESG metrics for project, business_unit, subsidiary or groups
    valid_levels = ["project", "business_unit", "subsidiary", "group"]
    if level.lower() not in valid_levels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level. Must be one of {valid_levels}",
        )
        
    metrics = get_rollup_by_level(db, level.lower(), entity_id)
    return {
        "level": level,
        "entity_id": entity_id,
        "summary": metrics,
    }