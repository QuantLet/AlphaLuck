PY ?= python3
.PHONY: all quantlets
all: quantlets
quantlets:
	$(PY) reproduce_quantlets.py
