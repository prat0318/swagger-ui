###
# swagger-ui-builder - https://github.com/wordnik/swagger-ui/
# Container for building the swagger-ui static site
#
# Build: docker build -t swagger-ui-builder .
# Run:   docker run -v $PWD/dist:/build/dist swagger-ui-builder
#
###

FROM    ubuntu:14.04
MAINTAINER dnephin@gmail.com

ENV     DEBIAN_FRONTEND noninteractive

RUN     apt-get update && \
        apt-get install -y \
                        git \
                        npm \
                        wget \
                        libpcre3 \
                        libpcre3-dev \
                        cron \
                        python-pip \
                        python-dev \
                        build-essential

# swagger-ui build
RUN     ln -s /usr/bin/nodejs /usr/local/bin/node
WORKDIR /build
ADD     package.json    /build/package.json
RUN     npm install
ADD     .   /build

# nginx
WORKDIR  /nginx
RUN     wget http://nginx.org/download/nginx-1.7.12.tar.gz
RUN     tar -xzvf nginx-1.7.12.tar.gz
RUN     git clone https://github.com/yaoweibin/ngx_http_substitutions_filter_module.git
WORKDIR  /nginx/nginx-1.7.12
RUN     ./configure --add-module=/nginx/ngx_http_substitutions_filter_module
RUN     make && make install
RUN     echo "\ndaemon off;" >> /usr/local/nginx/conf/nginx.conf

ADD     crontab /etc/cron.d/swagger-cron
RUN     chmod 0744 /etc/cron.d/swagger-cron

VOLUME  /nail/srv/configs
VOLUME  /nail/etc/services 

RUN     pip install pyyaml
ENV     PATH /usr/local/nginx/sbin:$PATH
RUN     touch /var/log/cron.log
EXPOSE  80
CMD     cron && nginx
