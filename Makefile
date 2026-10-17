.PHONY: setup test demo
setup:
	python3 -m pip install -e '.[dev]'
test:
	python3 -m pytest -q
demo:
	historyforgeai run --topic "Ashoka and the Kalinga War" --provider mock --no-assets --no-audio
