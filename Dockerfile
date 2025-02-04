FROM quay.io/redhat-cop/python-kopf-s2i:v1.34

USER root

COPY . /tmp/src

RUN rm -rf /tmp/src/.git* && \
    chown -R 1001 /tmp/src && \
    chgrp -R 0 /tmp/src && \
    chmod -R g+w /tmp/src && \
    cp -rp /tmp/src/.s2i/bin /tmp/scripts

USER 1001

RUN /tmp/scripts/assemble

CMD ["/tmp/scripts/run"]
