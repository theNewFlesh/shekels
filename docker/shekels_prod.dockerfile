FROM ubuntu:18.04 as base

USER root

# coloring syntax for headers
ENV CYAN='\033[0;36m'
ENV NO_COLOR='\033[0m'
ENV DEBIAN_FRONTEND='noninteractive'

# setup ubuntu user
ARG UID_='1000'
ARG GID_='1000'
RUN echo "\n${CYAN}SETUP UBUNTU USER${NO_COLOR}"; \
    addgroup --gid $GID_ ubuntu && \
    adduser \
    --disabled-password \
    --gecos '' \
    --uid $UID_ \
    --gid $GID_ ubuntu
WORKDIR /home/ubuntu

# update ubuntu and install basic dependencies
RUN echo "\n${CYAN}INSTALL GENERIC DEPENDENCIES${NO_COLOR}"; \
    apt update && \
    apt install -y \
        python3-dev \
        software-properties-common \
        wget

# install python3.7 and pip
RUN echo "\n${CYAN}SETUP PYTHON3.7${NO_COLOR}"; \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt update && \
    apt install -y python3.7 && \
    wget https://bootstrap.pypa.io/get-pip.py && \
    python3.7 get-pip.py && \
    rm -rf /home/ubuntu/get-pip.py

# install shekels
ENV REPO='shekels'
ENV PYTHONPATH "${PYTHONPATH}:/home/ubuntu/$REPO/python"
RUN echo "\n${CYAN}INSTALL $REPO${NO_COLOR}"; \
    apt update && \
    apt install -y \
        graphviz \
        python3-pydot && \
    pip3.7 install shekels>=1.0.2;

ENTRYPOINT [\
    "python3.7",\
    "/home/ubuntu/.local/lib/python3.7/site-packages/shekels/server/app.py"\
]
