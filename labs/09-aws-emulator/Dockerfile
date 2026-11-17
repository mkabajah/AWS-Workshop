# Lab 09 · AWS Emulator in a container (macOS, Windows, or Linux with Docker).
# From the AWS Emulator user guide, "Getting started with Docker".
#
#   Intel / AMD:              docker build -t aws-emulator labs/09-aws-emulator
#   Apple silicon / Arm:      docker build --build-arg ARCH=aarch64 -t aws-emulator labs/09-aws-emulator

FROM public.ecr.aws/amazonlinux/amazonlinux:2023-minimal
ARG ARCH=x86_64
ADD https://downloads.aws.com/aws-emulator/packages/aws-emulator/LTS/latest/aws-emulator-${ARCH}.rpm /tmp/aws-emulator.rpm
RUN rpm -i /tmp/aws-emulator.rpm && rm /tmp/aws-emulator.rpm \
    && mkdir -p /home/emulator && chown 1000 /home/emulator
USER 1000
ENV HOME=/home/emulator
EXPOSE 9297
ENTRYPOINT ["aws-emulator", "-b", "0.0.0.0"]
