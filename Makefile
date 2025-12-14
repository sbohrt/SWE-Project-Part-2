#
# SAM makefile build for ModelRatingAPI
# This packages only the backend (src + lambda + deps) to keep the Lambda
# artifact small. Frontend and other large dirs are excluded.
#

.PHONY: build-ModelRatingAPI

build-ModelRatingAPI:
	@echo "==> Building ModelRatingAPI into $(ARTIFACTS_DIR)"
	rm -rf "$(ARTIFACTS_DIR)"
	mkdir -p "$(ARTIFACTS_DIR)"
	# Copy backend source and lambda handler
	rsync -av --exclude '__pycache__' --exclude '*.pyc' --exclude '*.pyo' \
		src lambda "$(ARTIFACTS_DIR)"/
	# Install Python deps into the artifact dir
	pip install -r requirements.txt -t "$(ARTIFACTS_DIR)"
	# Copy requirements for reference (optional)
	cp requirements.txt "$(ARTIFACTS_DIR)"/


