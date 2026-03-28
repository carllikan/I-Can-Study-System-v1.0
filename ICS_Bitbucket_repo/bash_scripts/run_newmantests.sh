#!/bin/bash

LOCATE_FILE=`which npm`
if [ "" == "$LOCATE_FILE" ]; then
    yum install -y node
else
    echo node and npm already installed
fi

LOCATE_FILE=`which newman`
if [ "" == "$LOCATE_FILE" ]; then
    npm install -g newman
else
    echo newman already installed
fi

newman run "../cloudrun_source/evaluation_api/AddAxis.ai ICS-AI-APIs.postman_collection.json"
