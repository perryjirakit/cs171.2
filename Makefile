
d ?= 10
epsilon_max ?= 0.1
rho ?= 1e-6

run_project:
	@set -e; \
	python3 time_server.py & ts=$$!; \
	python3 network.py & nw=$$!; \
	rc=0; python3 client.py --d $(d) --epsilon $(epsilon_max) --rho $(rho) --csv output.csv || rc=$$?; \
	kill $$nw $$ts 2>/dev/null || true; \
	wait $$nw $$ts 2>/dev/null || true; \
	exit $$rc
