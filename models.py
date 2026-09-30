from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from database import Base
from sqlalchemy.orm import relationship

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    subsidiaries = relationship("Subsidiary", back_populates="group")
    
class Subsidiary(Base):
    __tablename__ = "subsidiaries"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    group =relationship("Group", back_populates="subsidiaries")
    business_units = relationship("BusinessUnit", back_populates="subsidiary")
    
class BusinessUnit(Base):
    __tablename__ = "business_units"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    subsidiary_id = Column(Integer, ForeignKey("subsidiaries.id"), nullable=False)
    subsidiary = relationship("Subsidiary", back_populates="business_units")
    projects = relationship("Project", back_populates="business_unit")
    
class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=False)
    business_unit=relationship("BusinessUnit", back_populates="projects")
    metrics = relationship("ESGMetricEntry", back_populates="project")
    
class ESGMetricEntry(Base):
    __tablename__ = "esg_metric_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    metric_type = Column(String, nullable=False)
    raw_value = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    normalized_value_mt = Column(Float, nullable=True)
    billing_period = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("Project", back_populates="metrics")