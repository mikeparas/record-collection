from pydantic import BaseModel


class HealthCheck(BaseModel):
    status: str
    component: str


class HealthChecks(BaseModel):
    database: HealthCheck
    queue: HealthCheck


class HealthStatus(BaseModel):
    status: str
    checks: HealthChecks | None
