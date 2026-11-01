FROM python@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS speech-build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake curl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN curl --fail --location --retry 3 https://github.com/ggml-org/whisper.cpp/archive/refs/tags/v1.9.5.tar.gz -o source.tar.gz \
 && echo 'ff1a9053feb509ff9d7729703355541ae9690073a6b1c40eb692c962e0dc1720  source.tar.gz' | sha256sum --check - \
 && tar -xzf source.tar.gz --strip-components=1 \
 && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DGGML_CUDA=OFF -DGGML_BLAS=OFF -DWHISPER_BUILD_TESTS=OFF \
 && cmake --build build --parallel 2 --target whisper-cli

FROM python@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgomp1 libstdc++6 ca-certificates && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2
WORKDIR /app
COPY server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt
COPY --from=speech-build /build/build/bin/whisper-cli /usr/local/bin/whisper-cli
COPY server /app/server
COPY content /app/content
COPY web /app/web
USER 996:987
EXPOSE 8788
CMD ["python", "server/run.py"]
