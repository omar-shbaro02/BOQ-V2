from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.generated import taxonomies
from app.routers.cases import router as cases_router
from app.routers.control_context import router as control_context_router
from app.routers.cost import router as cost_router
from app.routers.evidence import router as evidence_router
from app.routers.forecast import router as forecast_router
from app.routers.governance import router as governance_router
from app.routers.impact import router as impact_router
from app.routers.orchestration import router as orchestration_router
from app.routers.progress import router as progress_router
from app.routers.schedule import router as schedule_router
from app.routers.signals import router as signals_router

settings = get_settings()
app = FastAPI(
    title="VAI Project Control Decision Intelligence API",
    version="0.1.0",
    description="Governed decision support. Recommendations never constitute human decisions.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=[
        "Content-Type",
        "Idempotency-Key",
        "X-VAI-Actor-ID",
        "X-VAI-Organization-ID",
        "X-VAI-Roles",
    ],
)
app.include_router(control_context_router)
app.include_router(evidence_router)
app.include_router(signals_router)
app.include_router(cases_router)
app.include_router(progress_router)
app.include_router(schedule_router)
app.include_router(cost_router)
app.include_router(forecast_router)
app.include_router(impact_router)
app.include_router(orchestration_router)
app.include_router(governance_router)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@app.get("/api/v1/meta/taxonomies", tags=["metadata"])
def get_taxonomies() -> dict[str, object]:
    names = (
        "SemanticState",
        "TruthType",
        "Disposition",
        "DecisionReadiness",
        "CaseLifecycle",
        "GovernanceState",
        "AutonomyClass",
        "ControlledObjectType",
        "ProgressBasis",
        "UrgencyLevel",
        "SpecialistKind",
        "SpecialistRunStatus",
        "OrchestrationStatus",
        "SpecialistContradictionType",
        "HumanDecisionAgreement",
        "AuthorityValidationOutcome",
        "ResponseExecutionStatus",
        "OutcomeClassification",
        "LearningCategory",
        "ProjectRole",
        "ControlledObjectRelationType",
        "AuthorizedContextType",
        "ProjectStatus",
        "EvidenceItemStatus",
        "EvidenceRelationType",
        "VerificationOutcome",
        "ContradictionStatus",
        "EvidenceRequestStatus",
        "ImportBatchStatus",
        "DataClassification",
        "SignalType",
        "SignalStatus",
        "ScreeningOutcome",
        "ScreeningReasonCode",
        "MaterialityBand",
        "CorrelationOutcome",
        "CorrelationReviewStatus",
        "ConclusionType",
        "BaselineValidity",
        "LimitationStatus",
        "LimitationCode",
        "ActiveResponseStatus",
        "CaseLedgerEventType",
        "CaseReopenTrigger",
        "ProgressMeasurementKind",
        "ProgressReconciliationStatus",
        "DeviationDirection",
        "TrendPersistence",
        "TrendDirection",
        "ScheduleDependencyType",
        "ScheduleConstraintType",
        "ScheduleQualityStatus",
        "ScheduleAssessmentStatus",
        "ScheduleTimingDirection",
        "FloatSource",
        "ScheduleExposureLevel",
        "ScheduleConclusion",
        "CostRecordKind",
        "CommercialEffectType",
        "CostAlignmentStatus",
        "CostAssessmentStatus",
        "CostForecastStatus",
        "CostConclusion",
        "ForecastTarget",
        "ForecastScenarioType",
        "ForecastMethod",
        "ForecastStatus",
        "ForecastValidity",
        "ForecastRecalculationTrigger",
        "ConsequenceType",
        "ConsequenceSeverity",
        "ImpactAssessmentStatus",
        "PriorityBand",
        "DecisionClockType",
    )
    return {
        "schema_version": taxonomies.SCHEMA_VERSION,
        "taxonomies": {
            name: [member.value for member in getattr(taxonomies, name)] for name in names
        },
    }
