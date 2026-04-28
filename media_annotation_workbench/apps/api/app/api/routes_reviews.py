from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session, require_roles
from app.models import User
from app.schemas import ReviewActionRequest, ReviewDraftUpdateRequest, ReviewMutationResponse, ReviewTaskDetailResponse, ReviewTaskListResponse
from app.services.assets import get_review_task_detail, list_review_tasks
from app.services.reviews import approve_review_task, build_mutation_payload, claim_review_task, return_review_task, save_review_draft, submit_review_task

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("/tasks", response_model=ReviewTaskListResponse)
def get_review_tasks(
    snapshot_id: str | None = None,
    search: str | None = None,
    review_status: str | None = None,
    creator_id: str | None = None,
    _current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReviewTaskListResponse:
    try:
        resolved_snapshot_id, items = list_review_tasks(
            session,
            snapshot_id=snapshot_id,
            search=search,
            filters={
                "review_status": review_status or "",
                "creator_id": creator_id or "",
            },
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    serialized = [item if hasattr(item, "review_task_id") else item for item in items]
    from app.services.assets import serialize_review_task

    return ReviewTaskListResponse(
        snapshot_id=resolved_snapshot_id,
        total=len(items),
        items=[serialize_review_task(session, task) for task in items],
    )


@router.get("/tasks/{review_task_id}", response_model=ReviewTaskDetailResponse)
def get_review_task(
    review_task_id: str,
    _current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReviewTaskDetailResponse:
    try:
        detail = get_review_task_detail(session, review_task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReviewTaskDetailResponse(**detail)


@router.post("/tasks/{review_task_id}/claim", response_model=ReviewMutationResponse)
def claim_task(
    review_task_id: str,
    current_user: User = Depends(require_roles("admin", "annotator")),
    session: Session = Depends(get_session),
) -> ReviewMutationResponse:
    try:
        task = claim_review_task(session, review_task_id, current_user)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReviewMutationResponse(**build_mutation_payload(session, task))


@router.post("/tasks/{review_task_id}/draft", response_model=ReviewMutationResponse)
def save_draft(
    review_task_id: str,
    payload: ReviewDraftUpdateRequest,
    current_user: User = Depends(require_roles("admin", "annotator")),
    session: Session = Depends(get_session),
) -> ReviewMutationResponse:
    try:
        task = save_review_draft(session, review_task_id, current_user, payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReviewMutationResponse(**build_mutation_payload(session, task))


@router.post("/tasks/{review_task_id}/submit", response_model=ReviewMutationResponse)
def submit_task(
    review_task_id: str,
    payload: ReviewActionRequest,
    current_user: User = Depends(require_roles("admin", "annotator")),
    session: Session = Depends(get_session),
) -> ReviewMutationResponse:
    try:
        task = submit_review_task(session, review_task_id, current_user, payload.review_notes)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReviewMutationResponse(**build_mutation_payload(session, task))


@router.post("/tasks/{review_task_id}/approve", response_model=ReviewMutationResponse)
def approve_task(
    review_task_id: str,
    payload: ReviewActionRequest,
    current_user: User = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> ReviewMutationResponse:
    try:
        task = approve_review_task(session, review_task_id, current_user, payload.review_notes)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReviewMutationResponse(**build_mutation_payload(session, task))


@router.post("/tasks/{review_task_id}/return", response_model=ReviewMutationResponse)
def return_task(
    review_task_id: str,
    payload: ReviewActionRequest,
    current_user: User = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> ReviewMutationResponse:
    try:
        task = return_review_task(session, review_task_id, current_user, payload.review_notes)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReviewMutationResponse(**build_mutation_payload(session, task))
