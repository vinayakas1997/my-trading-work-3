# syntax=docker/dockerfile:1
#
# Builds llama.cpp's `llama-server` from source with CUDA support, rather
# than trusting a prebuilt ghcr.io/ggml-org/llama.cpp:server-cuda tag --
# 2026 reports (Qwen3.6's new rope-encoding format breaking every existing
# llama.cpp docker image on release day) confirm floating server-cuda tags
# lag behind new model architectures. Building from a pinned commit here
# means this image can be rebuilt against a newer llama.cpp checkout the
# same day a new Qwen release needs it, without waiting on someone else's
# image republish.
#
# Serves Qwen3.5-4B-Q4_K_M.gguf (or any other single-file GGUF dropped into
# the mounted models/ dir) over llama.cpp's own OpenAI-compatible
# /v1/chat/completions endpoint -- the exact shape Hindsight's
# HINDSIGHT_API_LLM_BASE_URL expects (see docker-compose-hindsight.yml).

FROM nvidia/cuda:12.4.1-devel-ubuntu22.04 AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
        git cmake build-essential curl libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# Pin to a specific release tag, not a branch -- reproducible builds, and
# an explicit, deliberate action (bump this tag) any time a new model
# architecture needs a newer llama.cpp, rather than silently picking up
# upstream's latest on every rebuild.
#
# b11065 (2026-09-20) chosen deliberately, not arbitrarily: Qwen3.5 uses a
# hybrid Gated-DeltaNet architecture (only 4 of 32 layers are standard
# full attention; the rest are a fixed-size recurrent linear-attention
# state) that llama.cpp only gained real support for via the
# GATED_DELTA_NET ggml op, ggml-org/llama.cpp#19504, merged 2026-03-07 --
# any tag before that (the earlier b4079 placeholder here included) cannot
# load this model's architecture at all. Verified working at this tag via
# a real documented run (`llama-server -hf unsloth/Qwen3.5-4B-GGUF -c
# 32000`, debuggercafe.com's Qwen3.5 writeup) -- not just "should work."
ARG LLAMA_CPP_REF=b11065
RUN git clone --depth 1 --branch ${LLAMA_CPP_REF} https://github.com/ggml-org/llama.cpp.git .

# ggml-cuda's CUDA Virtual Memory Management path (cuMemCreate/cuMemMap/
# cuDeviceGet/... -- real CUDA Driver API calls, distinct from the Runtime
# API) needs libcuda.so at link time. The devel image only ships a
# compile-time stub under a non-default search path, and adding that path
# via -L alone isn't enough without an explicit -lcuda too (confirmed by
# an actual failed build: adding just -L still left every cu* driver
# symbol undefined). GGML_CUDA_NO_VMM=ON disables this feature at build
# time instead -- llama.cpp's own documented workaround for this exact
# link failure -- so no driver library is needed at all here; it only
# affects a memory-pooling optimization, not whether inference works at
# runtime once the real driver is present via --gpus.
RUN cmake -B build -DGGML_CUDA=ON -DGGML_CUDA_NO_VMM=ON -DLLAMA_CURL=ON \
        -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build --config Release --target llama-server -j"$(nproc)"

FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 libcurl4 curl \
    && rm -rf /var/lib/apt/lists/*

# llama.cpp builds llama-server against several sibling shared libraries
# (libllama-server-impl.so, libggml*.so, libllama.so, ...) in the same
# build/bin/ directory -- copying only the executable produces a real,
# confirmed "error while loading shared libraries: libllama-server-impl.so:
# cannot open shared object file" at container startup. Copy the whole
# directory instead and let ldconfig register it.
COPY --from=build /src/build/bin/ /usr/local/lib/llama.cpp/
RUN ln -s /usr/local/lib/llama.cpp/llama-server /usr/local/bin/llama-server \
    && echo "/usr/local/lib/llama.cpp" > /etc/ld.so.conf.d/llama-cpp.conf \
    && ldconfig

WORKDIR /models
VOLUME /models

ENV LLAMA_MODEL_FILE=Qwen3.5-4B-Q4_K_M.gguf \
    LLAMA_CTX_SIZE=32768 \
    LLAMA_N_GPU_LAYERS=999 \
    LLAMA_PORT=8080

EXPOSE 8080

# --n-gpu-layers 999 offloads every layer it can -- a Q4_K_M 4B model fits
# entirely on any GPU with a few GB free, so this is safe by default; drop
# it via LLAMA_N_GPU_LAYERS=0 for a CPU-only run of this same image.
ENTRYPOINT ["/bin/sh", "-c", "exec llama-server -m /models/${LLAMA_MODEL_FILE} -c ${LLAMA_CTX_SIZE} -ngl ${LLAMA_N_GPU_LAYERS} --host 0.0.0.0 --port ${LLAMA_PORT}"]
