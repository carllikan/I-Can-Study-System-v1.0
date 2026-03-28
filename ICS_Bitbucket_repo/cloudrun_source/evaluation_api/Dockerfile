FROM python:3.10-slim
# Create app directory
WORKDIR /app

# Install app dependencies
COPY requirements.txt ./

RUN pip install -r requirements.txt
RUN pip install torch==2.0.0 torchvision==0.15.0 torchaudio==2.0.0 -f https://download.pytorch.org/whl/cpu/torch_stable.html
# Set the Enviromental Variables

ARG REF_URL
ARG MM_URL


ENV REF_URL ${REF_URL}
ENV MM_URL ${MM_URL} 

# Bundle app source
COPY . .

EXPOSE 8080
CMD [ "flask", "run","--host","0.0.0.0","--port","8080"]