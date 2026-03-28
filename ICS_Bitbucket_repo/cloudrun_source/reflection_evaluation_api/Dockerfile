FROM python:3.10-slim
# Create app directory
WORKDIR /app

# Install app dependencies
COPY requirements.txt ./

RUN pip install -r requirements.txt

ARG ICS_REFLECTION_EVALUATION_CLOUD_RUN_URL
ENV ICS_REFLECTION_EVALUATION_CLOUD_RUN_URL $ICS_REFLECTION_EVALUATION_CLOUD_RUN_URL
# Bundle app source
COPY . .

EXPOSE 8080
CMD [ "flask", "run","--host","0.0.0.0","--port","8080"]
