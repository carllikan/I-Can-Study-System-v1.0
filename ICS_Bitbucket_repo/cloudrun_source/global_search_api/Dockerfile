# Stage 1: Build stage
FROM python:3.11-slim as builder

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Download and install zlib
WORKDIR /tmp
RUN wget http://zlib.net/zlib-1.3.tar.gz && \
    tar -xvf zlib-1.3.tar.gz && \
    cd zlib-1.3 && \
    ./configure && \
    make && \
    make install

# Stage 2: Final stage
FROM python:3.11-slim

# Copy zlib from the builder stage
COPY --from=builder /usr/local/lib/libz.* /usr/local/lib/
COPY --from=builder /usr/local/include/zlib.h /usr/local/include/
COPY --from=builder /usr/local/include/zconf.h /usr/local/include/

# Create app directory
WORKDIR /app

# Install app dependencies
COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

ARG OPENAI_API_KEY
ARG PINECONE_API_KEY
ARG PINECONE_ENV
ENV OPENAI_API_KEY $OPENAI_API_KEY
ENV PINECONE_API_KEY $PINECONE_API_KEY
ENV PINECONE_ENV $PINECONE_ENV

# Bundle app source
COPY . .

EXPOSE 8080
CMD [ "flask", "run","--host","0.0.0.0","--port","8080"]
