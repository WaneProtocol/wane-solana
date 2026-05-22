# Wane ??build / test / lint shortcuts.
.PHONY: build test fmt lint clean engine cli sdk docker dev release

build: engine cli sdk

engine:
	anchor build

cli:
	cargo build --release -p wane-cli

sdk:
	cd sdk && npm install && npm run build

test:
	cargo test --workspace --exclude wane --exclude wane_vault
	cd sdk && npm test

fmt:
	cargo fmt --all
	cd sdk && npm run format

lint:
	cargo fmt --all -- --check
	cargo clippy --workspace -- -W warnings
	cd sdk && npm run lint

clean:
	cargo clean
	rm -rf sdk/dist sdk/node_modules .anchor target

docker:
	docker build -t wane-cli:dev .

dev:
	cd sdk && npm run build -- --watch

release:
	@echo "tag the current commit then run: gh release create v$$(cat .version) --generate-notes"
