from __future__ import annotations

import io
import os
import signal
from dataclasses import dataclass
from typing import Callable

import pytest

from meminit.cli.streaming import (
    StreamEmitter,
    SummaryPayload,
    streaming_output_handler,
)
from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.exit_codes import exit_code_for_error
from tests.cli.streaming_helpers import records

RUN_ID = "11111111-1111-4111-8111-111111111111"


@dataclass(frozen=True)
class CallableStreamingProducer:
    func: Callable[[StreamEmitter], SummaryPayload]

    def produce(self, emit: StreamEmitter) -> SummaryPayload:
        return self.func(emit)


def test_stream_emitter_sequences_and_counts(stream_schema_validator):
    stream = io.StringIO()
    emitter = StreamEmitter(command="scan", run_id=RUN_ID, stream=stream)

    emitter.emit_item("file", {"path": "docs/a.md"})
    emitter.emit_item("file", {"path": "docs/b.md"})
    emitter.emit_item("suggestion", {"code": "SUGGESTION"})
    emitter.emit_summary(SummaryPayload(data={"files_scanned": 2}))

    parsed = records(stream.getvalue())
    assert [record["sequence"] for record in parsed] == [0, 1, 2, 3, 4]
    assert parsed[-1]["counts"] == {"file": 2, "suggestion": 1}
    assert all(not list(stream_schema_validator.iter_errors(record)) for record in parsed)


def test_stream_emitter_rejects_records_after_terminal_summary():
    stream = io.StringIO()
    emitter = StreamEmitter(command="scan", run_id=RUN_ID, stream=stream)
    emitter.emit_summary(SummaryPayload())

    with pytest.raises(RuntimeError):
        emitter.emit_item("file", {"path": "docs/a.md"})


def test_streaming_output_handler_emits_meminit_error(capsys):
    def produce(_emit: StreamEmitter) -> SummaryPayload:
        raise MeminitError(ErrorCode.FILE_NOT_FOUND, "missing")

    with pytest.raises(SystemExit) as exc_info:
        streaming_output_handler(
            command="scan",
            producer=CallableStreamingProducer(produce),
            output=None,
            include_timestamp=False,
            run_id=RUN_ID,
        )

    assert exc_info.value.code == exit_code_for_error(ErrorCode.FILE_NOT_FOUND)
    parsed = records(capsys.readouterr().out)
    assert parsed[-1]["record_type"] == "error"
    assert parsed[-1]["error"]["code"] == ErrorCode.FILE_NOT_FOUND.value


def test_streaming_output_handler_emits_producer_failure(capsys):
    def produce(_emit: StreamEmitter) -> SummaryPayload:
        raise RuntimeError("boom")

    with pytest.raises(SystemExit) as exc_info:
        streaming_output_handler(
            command="scan",
            producer=CallableStreamingProducer(produce),
            output=None,
            include_timestamp=False,
            run_id=RUN_ID,
        )

    assert exc_info.value.code == exit_code_for_error(ErrorCode.STREAM_PRODUCER_FAILED)
    parsed = records(capsys.readouterr().out)
    assert parsed[-1]["record_type"] == "error"
    assert parsed[-1]["error"]["code"] == ErrorCode.STREAM_PRODUCER_FAILED.value


@pytest.mark.skipif(
    os.getenv("PYTEST_XDIST_WORKER") is not None,
    reason="signal test incompatible with xdist worker process signalling",
)
def test_streaming_output_handler_emits_interrupted_record(capsys):
    original_sigint = signal.getsignal(signal.SIGINT)
    original_sigterm = signal.getsignal(signal.SIGTERM)

    def produce(_emit: StreamEmitter) -> SummaryPayload:
        os.kill(os.getpid(), signal.SIGINT)
        return SummaryPayload()

    with pytest.raises(SystemExit) as exc_info:
        streaming_output_handler(
            command="scan",
            producer=CallableStreamingProducer(produce),
            output=None,
            include_timestamp=False,
            run_id=RUN_ID,
        )

    assert exc_info.value.code == 130
    parsed = records(capsys.readouterr().out)
    assert parsed[-1]["record_type"] == "error"
    assert parsed[-1]["error"]["code"] == ErrorCode.STREAM_INTERRUPTED.value
    assert signal.getsignal(signal.SIGINT) == original_sigint
    assert signal.getsignal(signal.SIGTERM) == original_sigterm
