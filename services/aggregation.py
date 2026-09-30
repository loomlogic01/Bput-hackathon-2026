from models import BusinessUnit, ESGMetricEntry, Group, Project, Subsidiary
from sqlalchemy import func
from sqlalchemy.orm import Session


def get_rollup_by_level(db: Session, level: str, entity_id: int):
    # aggregates esg metric totals for different levels
    query = db.query(
        ESGMetricEntry.metric_type,
        func.sum(ESGMetricEntry.raw_value).label("total_raw"),
        func.sum(ESGMetricEntry.normalized_value_mt).label("total_mt"),
        ESGMetricEntry.unit,
    )
    
    if level == "project":
        query = query.filter(ESGMetricEntry.project_id == entity_id)
        
    elif level == "business_unit":
        query = query.join(Project).filter(Project.business_unit_id == entity_id)
        
    elif level == "subsidiary":
        query = query.join(Project).join(BusinessUnit).filter(BusinessUnit.subsidiary_id == entity_id)
        
    elif level == "group":
        query = query.join(Project).join(BusinessUnit).join(Subsidiary).filter(Subsidiary.group_id == entity_id)
        
    else:
        raise ValueError("Invalid hierarchy level")
    
    results = query.group_by(
        ESGMetricEntry.metric_type, ESGMetricEntry.unit
    ).all()
    
    return [
        {
            "metric_type": r.metric_type,
            "total_raw_value": r.total_raw,
            "total_mt": r.total_mt,
            "unit": r.unit,
        }
        for r in results
    ]