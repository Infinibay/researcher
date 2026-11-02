"""Original-owned Git validation and confirmation around one sealed native review.

The host retains its actual process domain through final Git. Neither model
tool calls nor a different owner can confirm, accept or publish this review.
"""

from backend.runtime.broker_git import OwnedGitExecutor
from backend.runtime.candidate_capture import closed_writer_proof
from backend.runtime.code_review_git import validate_review_candidate
from backend.runtime.code_review_records import CodeReviewRecords
from backend.runtime.contracts import RunConflict, RunNotFound


async def prepare_owned_review(lease, *, runs, owner, registry, asset, settled):
    """Reserve before effects, validate exact candidate bytes once and bind actual original-owner receipts before native startup."""
    records = CodeReviewRecords(runs)
    _planned, created = await settled(records.reserve, lease)
    if not created:
        raise RunConflict(
            "Original native review already reserved; inspect its records without replay"
        )
    try:
        candidate = await settled(records.candidate, lease)
        executor = OwnedGitExecutor(
            owner=owner,
            registry=registry,
            lease=lease,
            source=candidate.workspace,
            allocation=None,
            asset=asset,
        )
        observed = await validate_review_candidate(candidate, executor=executor)
        proof = await settled(closed_writer_proof, owner, lease)
        await settled(records.preflight, lease, observed, proof)
        return records, executor
    except BaseException as error:
        owner.broker.withdraw()
        await owner.aclose()
        await settled(
            records.observe_failure,
            lease,
            "Review preparation interrupted: " + type(error).__name__,
        )
        raise


async def confirm_owned_review(lease, *, records, executor, session, owner, settled):
    """Seal native/tools/Ken, revalidate Git under the same physical owner and confirm only the unchanged original proposal."""
    try:
        await session.seal()
        candidate = await settled(records.candidate, lease)
        observed = await validate_review_candidate(candidate, executor=executor)
        proof = await settled(closed_writer_proof, owner, lease)
        return await settled(records.confirm, lease, observed, proof)
    except BaseException as error:
        owner.broker.withdraw()
        await owner.aclose()
        try:
            await settled(
                records.observe_failure,
                lease,
                "Review confirmation interrupted: " + type(error).__name__,
            )
        except RunNotFound:
            pass
        raise
