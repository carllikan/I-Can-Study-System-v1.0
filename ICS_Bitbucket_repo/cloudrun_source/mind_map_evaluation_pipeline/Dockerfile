FROM python:3.10-slim


RUN apt-get update && apt-get install -y \
     libglib2.0-0


# Create app directory
WORKDIR /app

# Install app dependencies
COPY requirements.txt ./
RUN pip install torch==2.0.0 torchvision==0.15.0 torchaudio==2.0.0 -f https://download.pytorch.org/whl/cpu/torch_stable.html
RUN pip install ultralytics==8.2.2
RUN pip install -r requirements.txt

# ARG DB_USER
# ARG DB_PASS
# ARG DB_NAME
# ARG PROJECT
# ARG REGION
# ARG INSTANCE_NAME
ARG AWS_ACCESS_KEY_ID
ARG AWS_SECRET_ACCESS_KEY
ARG FINAL_FEEDBACK_CLOUD_RUN_URL
ARG HF_ACCESS_TOKEN
# ENV DB_USER ${DB_USER:-ics-admin}
# ENV DB_PASS ${DB_PASS:-ics-ai-jobs}
# ENV DB_NAME ${DB_NAME:-ics-ai-jobs-database}
# ENV INSTANCE_NAME ${INSTANCE_NAME:-ics-ai-jobs}
# ENV PROJECT ${PROJECT}
# ENV REGION ${REGION}
ENV AWS_ACCESS_KEY_ID $AWS_ACCESS_KEY_ID
ENV AWS_SECRET_ACCESS_KEY $AWS_SECRET_ACCESS_KEY
ENV FINAL_FEEDBACK_CLOUD_RUN_URL $FINAL_FEEDBACK_CLOUD_RUN_URL
ENV HF_ACCESS_TOKEN $HF_ACCESS_TOKEN



# Bundle app source
COPY . .

EXPOSE 8080
CMD [ "flask", "run","--host","0.0.0.0","--port","8080"]