.PHONY: help install demo test lint bench clean

help:
	@echo "make install  安装依赖（uv sync 或 pip install -e .[dev]）"
	@echo "make demo     跑通端到端最小闭环"
	@echo "make test     跑单测"
	@echo "make lint     跑 ruff + mypy"
	@echo "make bench    跑评测（LoCoMo 对比 baseline）"

install:
	uv sync --all-extras || pip install -e ".[dev]"

demo:
	python -m yanji.demo

test:
	pytest python/tests -q

lint:
	ruff check python && mypy python/yanji

bench:
	python bench/locomo.py --compare-baseline

clean:
	rm -rf build dist .pytest_cache .mypy_cache
