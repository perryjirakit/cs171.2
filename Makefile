# Note that for autograder reasons,
# the following variable must
# be spelled exactly PORT!
PORT1 ?= 8001
PORT2 ?= 8002
PORT3 ?= 8003
PORT ?= 8004

.PHONY: run_clients stop

# Run all clients and master sequentially
run_clients:
	python3 client1.py -port $(PORT1) -client 1 & echo $$! > pids.txt; \
	sleep 1; \
	python3 client2.py -port $(PORT2) -client 2 & echo $$! >> pids.txt; \
	sleep 1; \
	python3 client3.py -port $(PORT3) -client 3 & echo $$! >> pids.txt; \
	sleep 2; \
	python3 master.py -port $(PORT) \
	-inputfile input.txt -outputfile output.txt & \
	echo $$! >> pids.txt
# Stop all running processes
stop:
	@echo "Killing processes..."
	@xargs kill < pids.txt || true
	@rm -f pids.txt

# C++ version equivalent to the Python Makefile
PORT1 ?= 8001
PORT2 ?= 8002
PORT3 ?= 8003
PORT ?= 8004

CXX := g++
CXXFLAGS := -std=c++17 -O2 -Wall -Wextra

CLIENT1_SRC := client1.cpp
CLIENT2_SRC := client2.cpp
CLIENT3_SRC := client3.cpp
MASTER_SRC := master.cpp

CLIENT1_BIN := client1
CLIENT2_BIN := client2
CLIENT3_BIN := client3
MASTER_BIN := master

.PHONY: compile run_clients stop clean

# Build all binaries
compile: $(CLIENT1_BIN) $(CLIENT2_BIN) $(CLIENT3_BIN) $(MASTER_BIN)
$(CLIENT1_BIN): $(CLIENT1_SRC)
$(CXX) $(CXXFLAGS) $< -o $@
$(CLIENT2_BIN): $(CLIENT2_SRC)
$(CXX) $(CXXFLAGS) $< -o $@
$(CLIENT3_BIN): $(CLIENT3_SRC)
$(CXX) $(CXXFLAGS) $< -o $@
$(MASTER_BIN): $(MASTER_SRC)
$(CXX) $(CXXFLAGS) $< -o $@

# Run all clients and master sequentially
run_clients: compile
	./$(CLIENT1_BIN) -port $(PORT1) -client 1 & echo $$! > pids.txt; \
	sleep 1; \
	./$(CLIENT2_BIN) -port $(PORT2) -client 2 & echo $$! >> pids.txt; \
	sleep 1; \
	./$(CLIENT3_BIN) -port $(PORT3) -client 3 & echo $$! >> pids.txt; \
	sleep 2; \
	./$(MASTER_BIN) -port $(PORT) \
	-inputfile input.txt -outputfile output.txt & \
	echo $$! >> pids.txt
# Stop all running processes
stop:
	@echo "Killing processes..."
	@xargs kill < pids.txt || true
	@rm -f pids.txt