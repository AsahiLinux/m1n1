FROM debian:buster-slim
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y build-essential bash git locales gcc-aarch64-linux-gnu libc6-dev-arm64-cross device-tree-compiler \
    && rm -rf /var/lib/apt/lists/* \
    && localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8
ENV LANG en_US.utf8

WORKDIR /m1n1
COPY . .

CMD ["/bin/bash"]
