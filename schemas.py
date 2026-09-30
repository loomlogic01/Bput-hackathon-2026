from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class UserRole(str, Enum):
    ADMIN = "Admin"
    ESG_OFFICER = " ESG officer"
    SUBIDIARY_MANAGER = "Subsidairy Manager"
    PROJECT_USER = "Project User"
    
class EntityType(str, Enum):
    GROUP = "GROUP"
    SUBSIDAIRY = "SUBSIDAITY"
    BUSINESS_UNIT = "BUSINESS_UNIT"
    PROJECT_SITE = "Project Site"
    
class MetricCategory(str, Enum):
    ENVIRONMENTAL = "Environmental"
    SOCIAL = "Social"
    GOVERNANCE = "Governance"
    
class SubmissionStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    
# User Schemas
class UserLogin(BaseModel):
    email: str
    password: str
    
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    
class UserResponse(BaseModel):
    id:str
    email: str
    role: UserRole
    assinged_entity_id: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
   
# Hierarchy Schemas 
class EntityCreate(BaseModel):
    name: str
    entity_type: EntityType
    parent_id: Optional[str] = None
    
class EntityResponse(BaseModel):
    id: str
    name: str
    entity_type: EntityType
    parent_id: Optional[str] = None
    children: List["EntityResponse"]
    
    model_config = ConfigDict(from_attributes=True)
    
# Matric submission schemas

class ESGMatricSubmit(BaseModel):
    catagory: MetricCategory = Field(..., description="Environmental, Social, or Government")
    metric_name: str = Field(..., description="e.g., Electricity Consumption, Worksite Incidents")
    raw_value: float = Field(..., description="15000.0")
    unit: str = Field(..., description="kWh, Liters, MT, Hours")
    reporting_period: str = Field(..., description="In Month Year format(e.g., September 2026)")
    evidence_file_path: Optional[str] = Field(None, description="Path to upload pdf/Image Proof")
    
class ESGMetricResponse(BaseModel):
    id: str
    entity_id: str
    category: MetricCategory
    metric_name: str
    raw_value: float
    unit: str
    reporting_period: str
    evidence_file_path: Optional[str]
    status: SubmissionStatus
    submitted_by: str
    varified_by: Optional[str]
    rejected_by: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attribute=True)
    
# Review Schemas
class ReviewAction(BaseModel):
    status: SubmissionStatus = Field(..., description="Accept (VERIFIED) or Rejected (REJECT)")
    rejection_reason: Optional[str] = Field(None, description="Mandatory if rejected")
    
class ParsedBillData(BaseModel):
    metric_name: str = Field(..., description="Identified metric e.g., ELECTRICITY, DIESEL, WATER")
    raw_value: float = Field(..., description="Extracted numerical consumption value")
    unit: str = Field(..., description="kWh, Liters, MT")
    reporting_period: Optional[str] = Field(None, description="Model Extraction Confidence")
    
# Dashboard Schemas
class MetricAggregatedSummary(BaseModel):
    metric_name: str
    total_value: float
    unit: str
    total_projects_reported: int
    
class DashboardResponse(BaseModel):
    entity_id: str
    entity_name: str
    reporting_period: str
    metric_summary: List[MetricAggregatedSummary]