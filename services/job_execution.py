"""Execucao compartilhada de jobs longos.

Este modulo concentra a coreografia que antes ficava nos chamadores:
fila de GPU, transicoes do JobManager, publicacao de eventos, cancelamento
cooperativo e finalizacao consistente.
"""
import asyncio
from typing import Any, AsyncIterator, Callable, Dict, Optional

from services.jobs import Job, JobManager, JobState, job_manager

GPU_WAITING_EVENT = {
    "type": "status",
    "message": "Na fila: aguardando outra tarefa pesada terminar...",
}

EventCallback = Callable[[Dict[str, Any]], None]
ExceptionCallback = Callable[[BaseException], None]
BeforeFinishCallback = Callable[[Job, JobState, Optional[str]], None]
GeneratorFactory = Callable[[Any], Any]
PublishCallback = Callable[[Dict[str, Any]], None]
BlockingJobRunner = Callable[[PublishCallback, Any], Any]


def state_from_event(event: Dict[str, Any]) -> tuple[Optional[JobState], Optional[str]]:
    event_type = event.get("type")
    if event_type == "done":
        return JobState.COMPLETED, None
    if event_type == "error":
        return JobState.FAILED, event.get("message")
    if event_type == "cancelled":
        return JobState.CANCELLED, None
    return None, None


async def run_sync_generator_job(
    job: Job,
    make_generator: GeneratorFactory,
    *,
    manager: JobManager = job_manager,
    acquire_gpu: bool = True,
    unfinished_state: JobState = JobState.CANCELLED,
    on_event: Optional[EventCallback] = None,
    on_exception: Optional[ExceptionCallback] = None,
    before_finish: Optional[BeforeFinishCallback] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Executa um gerador sincrono e emite seus eventos como async iterator."""
    loop = asyncio.get_running_loop()
    final_state: Optional[JobState] = None
    error_message: Optional[str] = None
    gpu_acquired = False

    try:
        if acquire_gpu:
            queued_notified = False
            while not job.cancel_event.is_set():
                gpu_acquired = await loop.run_in_executor(
                    None,
                    manager.try_acquire_gpu,
                    job.job_id,
                    0.5,
                )
                if gpu_acquired:
                    break
                if not queued_notified:
                    queued_notified = True
                    waiting_event = dict(GPU_WAITING_EVENT)
                    manager.publish(job.job_id, waiting_event)
                    if on_event is not None:
                        on_event(waiting_event)
                    yield waiting_event

        if job.cancel_event.is_set():
            final_state = JobState.CANCELLED
            cancelled_event = {
                "type": "cancelled",
                "message": "Tarefa cancelada antes do inicio.",
            }
            manager.publish(job.job_id, cancelled_event)
            if on_event is not None:
                on_event(cancelled_event)
            yield cancelled_event
            return

        manager.start(job.job_id)
        sync_generator = make_generator(job.cancel_event)

        while True:
            event = await loop.run_in_executor(None, lambda: next(sync_generator, None))
            if event is None:
                break

            manager.publish(job.job_id, event)
            event_state, event_error = state_from_event(event)
            if event_state is not None:
                final_state = event_state
                error_message = event_error
            if on_event is not None:
                on_event(event)
            yield event

            if event.get("type") == "cancelled":
                break
            await asyncio.sleep(0.01)

    except Exception as exc:
        final_state = JobState.FAILED
        error_message = str(exc)
        if on_exception is not None:
            on_exception(exc)
        error_event = {"type": "error", "message": str(exc)}
        manager.publish(job.job_id, error_event)
        if on_event is not None:
            on_event(error_event)
        yield error_event
    finally:
        if gpu_acquired:
            manager.release_gpu(job.job_id)
        if final_state is None:
            job.cancel_event.set()
            final_state = unfinished_state
        if before_finish is not None:
            before_finish(job, final_state, error_message)
        manager.finish(job.job_id, final_state, error=error_message)


def run_blocking_job(
    job: Job,
    run: BlockingJobRunner,
    *,
    manager: JobManager = job_manager,
    cancelled_exceptions: tuple[type[BaseException], ...] = (),
    success_event_factory: Optional[Callable[[Any], Dict[str, Any]]] = None,
    cancelled_event_factory: Optional[Callable[[BaseException | None], Dict[str, Any]]] = None,
    error_event_factory: Optional[Callable[[BaseException], Dict[str, Any]]] = None,
    result_summary_factory: Optional[Callable[[Any], Optional[Dict[str, Any]]]] = None,
    on_exception: Optional[ExceptionCallback] = None,
    before_finish: Optional[BeforeFinishCallback] = None,
    unfinished_state: JobState = JobState.CANCELLED,
) -> None:
    """Executa um job bloqueante com publicacao e finalizacao consistentes."""
    final_state: Optional[JobState] = None
    error_message: Optional[str] = None
    result_summary: Optional[Dict[str, Any]] = None

    def publish(event: Dict[str, Any]) -> None:
        manager.publish(job.job_id, event)

    try:
        if job.cancel_event.is_set():
            final_state = JobState.CANCELLED
            if cancelled_event_factory is not None:
                publish(cancelled_event_factory(None))
            return

        manager.start(job.job_id)
        result = run(publish, job.cancel_event)

        if job.cancel_event.is_set():
            final_state = JobState.CANCELLED
            if cancelled_event_factory is not None:
                publish(cancelled_event_factory(None))
            return

        final_state = JobState.COMPLETED
        if result_summary_factory is not None:
            result_summary = result_summary_factory(result)
        if success_event_factory is not None:
            publish(success_event_factory(result))
    except cancelled_exceptions as exc:
        final_state = JobState.CANCELLED
        if cancelled_event_factory is not None:
            publish(cancelled_event_factory(exc))
    except Exception as exc:
        final_state = JobState.FAILED
        error_message = str(exc)
        if on_exception is not None:
            on_exception(exc)
        if error_event_factory is not None:
            publish(error_event_factory(exc))
        else:
            publish({"type": "error", "message": str(exc)})
    finally:
        if final_state is None:
            job.cancel_event.set()
            final_state = unfinished_state
        if before_finish is not None:
            before_finish(job, final_state, error_message)
        manager.finish(
            job.job_id,
            final_state,
            error=error_message,
            result_summary=result_summary,
        )
