
import multiprocessing
import os
import time
import pytest
from pathlib import Path
from meminit.core.use_cases.new_document import NewDocumentUseCase, NewDocumentParams

def create_doc_worker(root_dir, title, results_queue):
    """Worker process to create a document."""
    try:
        use_case = NewDocumentUseCase(root_dir)
        params = NewDocumentParams(
            doc_type="ADR",
            title=title,
            owner="Worker",
            dry_run=False
        )
        result = use_case.execute_with_params(params)
        results_queue.put({
            "success": result.success,
            "document_id": result.document_id,
            "error": str(result.error) if result.error else None
        })
    except Exception as e:
        results_queue.put({"success": False, "error": str(e)})

def test_id_allocation_contention_multi_process(tmp_path):
    """P5.2: Multi-process contention test for ID allocation.
    Ensures that multiple concurrent processes creating documents of the same type
    do not receive duplicate IDs.
    """
    # 1. Setup repo
    gov_dir = tmp_path / "docs" / "00-governance"
    gov_dir.mkdir(parents=True)
    (gov_dir / "metadata.schema.json").write_text("{}")
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: Contention\nrepo_prefix: CON\ndocops_version: '2.0'\n"
        "document_types:\n  ADR: {directory: docs/adr}\n"
    )
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    
    # 2. Launch multiple workers
    num_workers = 10
    results_queue = multiprocessing.Queue()
    processes = []
    
    for i in range(num_workers):
        p = multiprocessing.Process(
            target=create_doc_worker,
            args=(str(tmp_path), f"Test Title {i}", results_queue)
        )
        processes.append(p)
        
    for p in processes:
        p.start()
        
    for p in processes:
        p.join()
        
    # 3. Collect results — expected count is fixed, so get exactly that many
    results = [results_queue.get() for _ in range(num_workers)]
        
    # 4. Verify
    assert len(results) == num_workers
    doc_ids = []
    errors = []
    for r in results:
        if r["success"]:
            doc_ids.append(r["document_id"])
        else:
            errors.append(r["error"])
            
    assert len(errors) == 0, f"Some workers failed: {errors}"
    assert len(doc_ids) == num_workers
    assert len(set(doc_ids)) == num_workers, f"Duplicate IDs detected! {doc_ids}"
    
    # Verify they are sequential (assuming empty repo to start)
    expected_ids = [f"CON-ADR-{i+1:03}" for i in range(num_workers)]
    assert sorted(doc_ids) == sorted(expected_ids)
