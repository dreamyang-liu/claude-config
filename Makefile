.PHONY: build test install clean

LINTERS := $(wildcard skills/*/scripts/*-lint.py profiles/*/skills/*/scripts/*-lint.py profiles/*/skills/*/scripts/svg-check.py)

build:
	go build -o bin/ccfg ./cmd/ccfg

test:
	gofmt -l . | tee /dev/stderr | test -z "$$(cat)"
	go vet ./...
	go test ./...
	@for s in $(LINTERS); do printf '%-72s ' "$$s"; python3 "$$s" --selftest | tail -1; done

install: build
	bin/ccfg install common --global

clean:
	rm -rf bin
