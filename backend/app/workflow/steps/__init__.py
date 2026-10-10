"""One handler per stage name, in the same order as STAGE_NAMES."""

from sqlalchemy.orm import Session

from app.models import STAGE_NAMES
from app.workflow.steps.chunk_formulary import chunk_formulary
from app.workflow.steps.embed_formulary import embed_formulary
from app.workflow.steps.extract_critical_points import extract_critical_points
from app.workflow.steps.extract_medications import extract_medications
from app.workflow.steps.finish_job import finish_job
from app.workflow.steps.parse_discharge import parse_discharge
from app.workflow.steps.summarize_discharge import summarize_discharge
from app.workflow.steps.verify_medications import verify_medications


def build_nodes(session: Session) -> dict:
    """Return the stage handlers in STAGE_NAMES order.

    The graph connects these keys in this order. Job creation writes the
    same names onto job_stages, so the screen and the worker stay aligned.
    """
    handlers = {
        "parsed": parse_discharge(session),
        "chunked": chunk_formulary(session),
        "embedded": embed_formulary(session),
        "summarized": summarize_discharge(session),
        "key_points": extract_critical_points(session),
        "entities": extract_medications(session),
        "verified": verify_medications(session),
        "done": finish_job(session),
    }
    if list(handlers) != list(STAGE_NAMES):
        raise RuntimeError("Workflow handlers must follow STAGE_NAMES")
    return handlers
