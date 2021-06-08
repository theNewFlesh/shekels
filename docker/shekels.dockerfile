FROM ubuntu:18.04

USER root

# coloring syntax for headers
ARG CYAN='\033[0;36m'
ARG NO_COLOR='\033[0m'
ARG DEBIAN_FRONTEND=noninteractive

# setup ubuntu user
ARG UID_='1000'
ARG GID_='1000'
RUN echo "\n${CYAN}SETUP UBUNTU USER${NO_COLOR}"; \
    addgroup --gid $GID_ ubuntu && \
    adduser \
        --disabled-password \
        --gecos '' \
        --uid $UID_ \
        --gid $GID_ ubuntu && \
    usermod -aG root ubuntu && \
    apt update && \
    apt install -y sudo && \
    echo "ubuntu ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers
WORKDIR /home/ubuntu

# update ubuntu and install basic dependencies
RUN echo "\n${CYAN}INSTALL GENERIC DEPENDENCIES${NO_COLOR}"; \
    apt update && \
    apt install -y \
        curl \
        git \
        parallel \
        pandoc \
        python3.7-dev \
        software-properties-common \
        tree \
        vim \
        wget

# install zsh
RUN echo "\n${CYAN}SETUP ZSH${NO_COLOR}"; \
    apt install -y zsh && \
    curl \
        -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh \
        -o install-oh-my-zsh.sh && \
    cd /root && \
    echo y | sh /home/ubuntu/install-oh-my-zsh.sh && \
    cp -r .oh-my-zsh /home/ubuntu

# install python3.7 and pip
RUN echo "\n${CYAN}SETUP PYTHON3.7${NO_COLOR}"; \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt update && \
    apt install -y python3.7 && \
    wget https://bootstrap.pypa.io/get-pip.py && \
    python3.7 get-pip.py

# DEBIAN_FRONTEND needed by texlive to install non-interactively
ARG DEBIAN_FRONTEND=noninteractive
RUN echo "\n${CYAN}INSTALL NODE.JS DEPENDENCIES${NO_COLOR}"; \
    curl -sL https://deb.nodesource.com/setup_10.x | bash - && \
    apt upgrade -y && \
    echo "\n${CYAN}INSTALL JUPYTERLAB DEPENDENCIES${NO_COLOR}"; \
    apt install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# install python dependencies
COPY ./dev_requirements.txt /home/ubuntu/dev_requirements.txt
COPY ./prod_requirements.txt /home/ubuntu/prod_requirements.txt
RUN echo "\n${CYAN}INSTALL PYTHON DEPENDECIES${NO_COLOR}"; \
    apt update && \
    apt install -y \
        chromium-chromedriver \
        graphviz \
        python3-pydot && \
    pip3.7 install -r dev_requirements.txt && \
    pip3.7 install -r prod_requirements.txt;

# configure zsh
RUN echo "\n${CYAN}CONFIGURE ZSH${NO_COLOR}"; \
    echo 'export PYTHONPATH="/home/ubuntu/shekels/python"' >> /home/ubuntu/.zshrc && \
    echo 'UTC' > /etc/timezone
COPY ./henanigans.zsh-theme /home/ubuntu/.oh-my-zsh/custom/themes/henanigans.zsh-theme
COPY ./zshrc /home/ubuntu/.zshrc

# install jupyter lab extensions
ENV NODE_OPTIONS="--max-old-space-size=8192"
RUN echo "\n${CYAN}INSTALL JUPYTER LAB EXTENSIONS${NO_COLOR}"; \
    jupyter labextension install \
        --dev-build=False \
        nbdime-jupyterlab \
        @oriolmirosa/jupyterlab_materialdarker \
        @ryantam626/jupyterlab_sublime \
        @jupyterlab/plotly-extension

RUN echo "\n${CYAN}FIX /HOME/UBUNTU PERMISSIONS${NO_COLOR}"; \
    chown -R ubuntu:ubuntu /home/ubuntu
ENV REPO_ENV=True
ENV PYTHONPATH "${PYTHONPATH}:/home/ubuntu/shekels/python"
ENV LANGUAGE "C"
ENV LC_ALL "C"
ENV LANG "C"
USER ubuntu
