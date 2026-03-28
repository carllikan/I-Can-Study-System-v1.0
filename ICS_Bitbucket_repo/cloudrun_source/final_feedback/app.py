from flask import Flask, request, jsonify, Response
from flask_utils import apply_security_headers
import os
import requests
import re
from datetime import datetime
from dotenv import load_dotenv
import logging 
from google.cloud import firestore
import pytz
from sql_orm import *
from std_response import *
from final_generator import FINALGenerator
load_dotenv()
logger = logging.getLogger()
app = Flask(__name__)
app.after_request(apply_security_headers)

@app.route('/', methods = ['POST'])

def main():

    if request.method != 'POST':
        return create_response('Please use POST to request the API', 405, request.method)
    
    aest = pytz.timezone('Australia/Sydney')
    PROJECT = os.getenv("PROJECT")
    # Validate the request
    now = datetime.now(aest)
    end_time = now.strftime("%Y-%m-%d %H:%M:%S")
    request_json = request.get_json(silent=True)
    logger.info(request_json)
    required_fields = ['mainjob-ID', 'user_id', 'component_list']
    
    for field in required_fields:
        # check whether required fields in request
        if field not in request_json:
            return create_response(f'Request must contain {field}', 400, request.method)
        if request_json[field] == "":
            return create_response(f'{field} must not be empty', 400, request.method)

    db_firestore = firestore.Client(PROJECT)
    final_generator = FINALGenerator()
    final_generator._update_firestore_data(db_firestore, request_json)
    logging.debug(request_json)
    logger.debug(request_json)
    # If all mindmaps, kolbs patterns are ready in firestore
    if final_generator._check_components(request_json):            
        update_job_status(request_json['mainjob-ID'], end_time)
        
        # Analyzing each principle level
        final_ans = final_generator._get_principles(request_json)
        db_firestore.collection("pending_feedback").document(request_json['mainjob-ID']).set(final_ans, merge=True)
        logger.info(f"Final response {final_ans} saving to firestore")
        callback(request_json['mainjob-ID'], request_json['user_id'], final_ans)
        return create_response('Feedback is complete and returning to Expert AI Endpoint', 200, request.method)

    return create_response('Feedback is still pending', 200, request.method)


def update_job_status(job_id,end_time):
    engine = initial_engine()
    try:
        #Update the Cloud SQL
        evalapi_update_query = {"job_id":job_id,
                                "end_timestamp":end_time}
        evalApiJobs_update(engine, evalapi_update_query)

    except Exception as e:
        logger.exception(e)
        return create_response("Unable to successfully Update Endtime of Main Eval!\
                        Please check the application logs for more details.", 500, request.method)


def is_valid_input(value):
    # This pattern ensures the value contains characters typically allowed in URLs and text.
    # Alphanumeric characters, hyphens, underscores, periods, and tildes are considered valid.
    pattern = re.compile("^[a-zA-Z0-9-_.~]+$")
    return bool(pattern.match(value))


def callback(mainjob_id, user_id, feedback):
    payload = {
        "job_id" : mainjob_id,
        "user_id" : user_id,
        "feedback": feedback
    }
    headers = {
        'Content-Type': 'application/json',
    }
    final_url = os.getenv("CALLBACK_URL")
    try:
        response = requests.post(final_url, headers=headers, json=payload, timeout=200)
        logger.warning(response)
    except requests.exceptions.ReadTimeout: 
        pass
    return