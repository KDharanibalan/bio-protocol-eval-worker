.PHONY: install test benchmark audit-demo docker-build

install:
	pip install -r requirements.txt

test:
	PYTHONPATH=src pytest -v

benchmark:
	PYTHONPATH=src python3 -m eval_worker.cli benchmark --enforce-gate

audit-demo:
	PYTHONPATH=src python3 -m eval_worker.cli audit data/sample_protocols/protocol_dex_safety_gap.md

docker-build:
	docker build -t bio-protocol-eval-worker:latest .
