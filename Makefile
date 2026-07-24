.PHONY: install data verify smoke eval ask test clean

install:      ## Create the venv and install dependencies (uv)
	uv sync

data:         ## (Re)generate the deterministic warehouse into warehouse/warehouse.duckdb
	uv run python -m cli data

verify:       ## Check the generated data against its ground truth
	uv run python -m cli verify

smoke:        ## Run the full eval on a deterministic mock model (no API key needed)
	uv run python -m cli run --mock

eval:         ## The real experiment: 6 rungs x {gpt-5.6-terra,gpt-5.4-mini} x 5 reps. Needs OPENAI_API_KEY.
	uv run python -m cli run --models gpt-5.6-terra,gpt-5.4-mini --repeats 5

# Ask one question, e.g.  make ask Q="how many active users?" RUNG=3 MODEL=gpt-5.6-terra
ask:
	uv run python -m cli ask --rung $(RUNG) --model $(MODEL) "$(Q)"

test:         ## Run the no-LLM test suite
	uv run python -m cli test

clean:        ## Remove the generated warehouse
	rm -f warehouse/warehouse.duckdb warehouse/warehouse.duckdb.wal
