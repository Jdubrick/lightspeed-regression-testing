#
#
# Copyright Red Hat
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
RAG_CONTENT_IMAGE ?= $(shell grep '^RAG_CONTENT_IMAGE=' ./compose/env/default-values.env | cut -d= -f2-)
CONTAINER_ENGINE ?= podman
COMPOSE ?= $(CONTAINER_ENGINE) compose
LOCAL_COMPOSE_PATH=./compose/compose.yaml

ENV_FILES := --env-file ./compose/env/default-values.env
ifneq ($(wildcard env/values.env),)
ENV_FILES += --env-file ./compose/env/values.env
endif

.PHONY: get-rag
get-rag: ## Download a copy of the RAG embedding model and vector database
	@$(CONTAINER_ENGINE) rm tmp-rag-container 2>/dev/null || true
	$(CONTAINER_ENGINE) create --name tmp-rag-container $(RAG_CONTENT_IMAGE) true
	rm -rf ./compose/rag-content
	mkdir -p ./compose/rag-content
	$(CONTAINER_ENGINE) cp tmp-rag-container:/rag/vector_db ./compose/rag-content
	$(CONTAINER_ENGINE) cp tmp-rag-container:/rag/embeddings_model ./compose/rag-content
	$(CONTAINER_ENGINE) rm tmp-rag-container
	chmod -R 777 ./compose/rag-content

.PHONY: compose-up
compose-up:
	$(COMPOSE) $(ENV_FILES) -f $(LOCAL_COMPOSE_PATH) up -d

.PHONY: compose-down
compose-down:
	$(COMPOSE) $(ENV_FILES) -f $(LOCAL_COMPOSE_PATH) down