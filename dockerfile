FROM ubuntu:22.04

RUN apt-get update && apt-get install -y\
    openssh-server\
    sudo\
    && mkdir /var/run/sshd

RUN useradd -m ubuntu && echo "ubuntu:password" | chpasswd && adduser ubuntu sudo


RUN sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

EXPOSE 22

CMD ["/usr/sbin/sshd", "-D"]