from sqlalchemy import Column, String, DateTime, JSON, Integer
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class WorkItem(Base):
    __tablename__ = "work_items"

    id = Column(String, primary_key=True)
    component_id = Column(String, index=True)
    status = Column(String, default="OPEN") # OPEN, INVESTIGATING, RESOLVED, CLOSED
    severity = Column(String) # P0, P1, P2
    start_time = Column(DateTime, default=datetime.utcnow) # First signal time
    end_time = Column(DateTime, nullable=True) # RCA submission time
    rca_data = Column(JSON, nullable=True) # Mandatory for CLOSED state
    
    @property
    def mttr_minutes(self):
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return round(delta.total_seconds() / 60, 2)
        return None