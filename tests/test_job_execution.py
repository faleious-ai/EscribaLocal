import asyncio

from services.job_execution import run_blocking_job, run_sync_generator_job
from services.jobs import JobManager, JobState


def _collect(job, make_generator, manager, **kwargs):
    async def run():
        events = []
        async for event in run_sync_generator_job(job, make_generator, manager=manager, **kwargs):
            events.append(event)
        return events

    return asyncio.run(run())


def test_run_sync_generator_job_finishes_completed(tmp_path):
    manager = JobManager(tmp_path / "history.jsonl")
    job = manager.create(kind="test")

    def generator(cancel_event):
        yield {"type": "status", "message": "inicio"}
        yield {"type": "progress", "progress": 50.0}
        yield {"type": "done", "full_transcript": []}

    events = _collect(job, generator, manager)
    snapshot = manager.get_snapshot(job.job_id)

    assert [event["type"] for event in events] == ["status", "progress", "done"]
    assert snapshot["state"] == "completed"
    assert snapshot["progress"] == 100.0
    assert manager.get(job.job_id).gpu_held is False


def test_run_sync_generator_job_cancelled_before_start(tmp_path):
    manager = JobManager(tmp_path / "history.jsonl")
    job = manager.create(kind="test")
    job.cancel_event.set()

    def generator(cancel_event):
        raise AssertionError("generator should not start")

    events = _collect(job, generator, manager)
    snapshot = manager.get_snapshot(job.job_id)

    assert events == [{"type": "cancelled", "message": "Tarefa cancelada antes do inicio."}]
    assert snapshot["state"] == "cancelled"


def test_run_sync_generator_job_exception_finishes_failed(tmp_path):
    manager = JobManager(tmp_path / "history.jsonl")
    job = manager.create(kind="test")

    def generator(cancel_event):
        yield {"type": "status", "message": "inicio"}
        raise RuntimeError("falha simulada")

    events = _collect(job, generator, manager)
    snapshot = manager.get_snapshot(job.job_id)

    assert [event["type"] for event in events] == ["status", "error"]
    assert events[-1]["message"] == "falha simulada"
    assert snapshot["state"] == "failed"
    assert snapshot["error"] == "falha simulada"


def test_run_sync_generator_job_can_default_unfinished_to_completed(tmp_path):
    manager = JobManager(tmp_path / "history.jsonl")
    job = manager.create(kind="test")

    def generator(cancel_event):
        yield {"type": "status", "message": "sem done explicito"}

    _collect(job, generator, manager, unfinished_state=JobState.COMPLETED)

    assert manager.get_snapshot(job.job_id)["state"] == "completed"


def test_run_blocking_job_finishes_completed(tmp_path):
    manager = JobManager(tmp_path / "history.jsonl")
    job = manager.create(kind="test")

    def runner(publish, cancel_event):
        publish({"type": "status", "message": "baixando"})
        return {"repo_used": "fake/repo"}

    run_blocking_job(
        job,
        runner,
        manager=manager,
        success_event_factory=lambda summary: {"type": "done", "result": summary},
        result_summary_factory=lambda summary: summary,
    )

    snapshot = manager.get_snapshot(job.job_id)
    assert snapshot["state"] == "completed"
    assert snapshot["result_summary"]["repo_used"] == "fake/repo"


def test_run_blocking_job_can_finish_cancelled(tmp_path):
    manager = JobManager(tmp_path / "history.jsonl")
    job = manager.create(kind="test")

    class FakeCancelled(Exception):
        pass

    def runner(publish, cancel_event):
        raise FakeCancelled("cancelado")

    run_blocking_job(
        job,
        runner,
        manager=manager,
        cancelled_exceptions=(FakeCancelled,),
        cancelled_event_factory=lambda _exc: {"type": "cancelled", "message": "cancelado"},
    )

    snapshot = manager.get_snapshot(job.job_id)
    assert snapshot["state"] == "cancelled"


def test_run_blocking_job_exception_finishes_failed(tmp_path):
    manager = JobManager(tmp_path / "history.jsonl")
    job = manager.create(kind="test")

    def runner(publish, cancel_event):
        raise RuntimeError("falha bloqueante")

    run_blocking_job(job, runner, manager=manager)

    snapshot = manager.get_snapshot(job.job_id)
    assert snapshot["state"] == "failed"
    assert snapshot["error"] == "falha bloqueante"
