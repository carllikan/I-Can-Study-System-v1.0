FROM python:3.10-slim
# Create app directory
WORKDIR /app

# Install app dependencies
COPY requirements.txt ./

RUN pip install -r requirements.txt

# Set the Enviromental Variables
# ARG DB_USER
# ARG DB_PASS
# ARG DB_NAME
# ARG INSTANCE_NAME
# ARG PROJECT
# ARG REGION
ARG FINAL_FEEDBACK_CLOUD_RUN_URL

# ENV DB_USER ${DB_USER:-ics-admin}
# ENV DB_PASS ${DB_PASS:-ics-ai-jobs}
# ENV DB_NAME ${DB_NAME:-ics-ai-jobs-database}
# ENV INSTANCE_NAME ${INSTANCE_NAME:-ics-ai-jobs}
# ENV PROJECT ${PROJECT}
# ENV REGION ${REGION}
ENV FINAL_FEEDBACK_CLOUD_RUN_URL $FINAL_FEEDBACK_CLOUD_RUN_URL 

# Bundle app source
COPY . .

EXPOSE 8080
CMD [ "flask", "run","--host","0.0.0.0","--port","8080"]