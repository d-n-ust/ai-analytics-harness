.PHONY: install data smoke eval ask clean

install:      ## Create the venv and install dependencies (uv)
	uv sync

data:         ## (Re)generate the deterministic messy warehouse into data/warehouse.duckdb
	uv run python run.py data

smoke:        ## Run the full eval with a deterministic mock model (no API key needed)
	uv run python run.py eval --mock

eval:         ## Run the real experiment: 25 questions x 5 rungs x {small,large}. Needs ANTHROPIC_API_KEY.
	uv run python run.py eval

# Ask one question at one rung, e.g.  make ask Q="how many active users?" RUNG=3 MODEL=small
ask:
	uv run python run.py ask --rung $(RUNG) --model $(MODEL) "$(Q)"

clean:        ## Remove the generated warehouse
	rm -f data/warehouse.duckdb data/warehouse.duckdb.wal
