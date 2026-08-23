FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
ARG RUST_TOOLCHAIN=1.85.0

RUN apt-get update && apt-get install -y build-essential bash curl git locales gcc-aarch64-linux-gnu libc6-dev-arm64-cross device-tree-compiler \
    && rm -rf /var/lib/apt/lists/* \
    && localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8

RUN curl -s https://sh.rustup.rs | bash -s -- -y \
    --default-toolchain ${RUST_TOOLCHAIN} \
    --target aarch64-unknown-none-softfloat

ENV LANG en_US.utf8
ENV PATH "/root/.cargo/bin:${PATH}"

WORKDIR /m1n1
COPY . .

CMD ["/bin/bash"]
