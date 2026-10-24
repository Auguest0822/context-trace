.PHONY: help install demo test lint accept accept-mcp bench

help:
	@echo "make install  安装 HTTP、MCP 与测试依赖"
	@echo "make demo     向已启动的 seekdb 写入幂等虚构演示数据"
	@echo "make test     运行 Python 单元测试"
	@echo "make lint     运行 ruff + mypy"
	@echo "make accept  在真实 seekdb 上逐项验收 HTTP 后端"
	@echo "make accept-mcp  验收 MCP 写入、HTTP 读回与 MCP 检索"
	@echo "make bench    在真实 seekdb 上运行 30 道固定问题评测"

install:
	python -m pip install -e ".[mcp,dev]"

demo:
	python -m yanji.store.seed_demo

test:
	python -m unittest discover -s python/tests -v

lint:
	ruff check python && mypy python/yanji

accept:
	python -m yanji.eval.live_acceptance

accept-mcp:
	python -m yanji.eval.mcp_acceptance

bench:
	python -m yanji.store.seed_demo --scope benchmark:context-trace-v1
	python -m yanji.eval.run_benchmark
