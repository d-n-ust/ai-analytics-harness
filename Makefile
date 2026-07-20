.PHONY: install data smoke eval ask clean

install:      ## Create the venv and install dependencies (uv)
	uv sync

data:         ## (Re)generate the deterministic messy warehouse into data/warehouse.duckdb
	uv run python run.py data

smoke:        ## Run the full eval with a deterministic mock model (no API key needed)
	uv run python run.py eval --mock

eval:         ## Run the real experiment: 6 rungs x {gpt-5.6-terra,gpt-5.4-mini} x 5 reps. Needs OPENAI_API_KEY.
	uv run python run.py eval --models gpt-5.6-terra,gpt-5.4-mini --repeats 5

# Ask one question at one rung, e.g.  make ask Q="how many active users?" RUNG=3 MODEL=gpt-5.6-terra
ask:
	uv run python run.py ask --rung $(RUNG) --model $(MODEL) "$(Q)"

clean:        ## Remove the generated warehouse
	rm -f data/warehouse.duckdb data/warehouse.duckdb.wal
