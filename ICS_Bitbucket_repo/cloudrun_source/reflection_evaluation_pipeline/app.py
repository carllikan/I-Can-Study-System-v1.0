import base64
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, Response
from flask_utils import apply_security_headers
from content_functions import *  # Note: Imported twice in original code, consider removing one
from reflective_functions import *  # Note: Imported twice in original code, consider removing one

from google.cloud import firestore
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import google.auth
from sql_orm import *
from std_response import create_response
import json
import logging
import os
import pytz
import re
import requests
import sqlalchemy
import uuid
import logging

load_dotenv()
logger = logging.getLogger()
aest = pytz.timezone('Australia/Sydney')
app = Flask(__name__)
app.after_request(apply_security_headers)

def clean(text):
    if text:
        text = text.replace('\n', '')
        
        # Remove non-alphanumeric characters
        text = re.sub(r'[^a-zA-Z0-9\s]', '', text)

        return text
    return

# Triggered by a change in a storage bucket
@app.route('/', methods = ['POST'])
def main():
    logging.info(f"checking the method {request.method}")
    if request.method != 'POST':
        return create_response("Please use POST to request the API", 405,request.method)
    func_conf = gcp_get_config()
    request_json = request.get_json(silent=True)
    
    now = datetime.now(aest)
    start_time = now.strftime("%Y-%m-%d %H:%M:%S")
    request_json = request.get_json(silent=True)
    if "message" in request_json:
        pubsub_message = request_json["message"]
        pubsub_message_decode = base64.b64decode(pubsub_message['data']).decode('utf-8')
        request_json = json.loads(pubsub_message_decode)
    user_id = request_json['user_id']
    logger.warning('Request Checked Start')

    if 'patterns' not in request_json:
        return create_response(f'Request must contain patterns', 400,request.method)
    
    if request_json['patterns'] is None or len(request_json['patterns']) == 0:
        return create_response(f'No patterns need to analyze', 200,request.method)
    
    logger.warning('Request Checked successfully')
    mainjob_id = request_json['mainjob-ID']
    if "reflection_job_id" in request_json:
        reflection_job_id = request_json["reflection_job_id"]
    else:
        reflection_job_id = str( uuid.uuid4())
    engine = initial_engine()
    try:
        component_insert_query = {"job_id":mainjob_id,
                                  "sub_component_type":"Reflection",
                                  "sub_component_job_id":reflection_job_id}
        
        evalApiComponentJobs_insert(engine, component_insert_query)
        eval_jobs_insert_query={"reflection_job_id": reflection_job_id,
                                "eval_job_id": mainjob_id,
                                "start_timestamp": start_time,
                                "request": json.dumps(request_json)

        }
        reflectionJobs_insert(engine, eval_jobs_insert_query)
    except Exception as e:
        logger.exception(e)

        return create_response("Unable to successfully Add to eval_api_component_jobs and reflection_jobs! Please check the application logs for more details.",
                               500,request.method)

    patterns = request_json['patterns']
    logging.info(f"patterns: {patterns}")
    Reflective_Pattern = ReflectivePattern()
    Content_Pattern = ContentbasePattern()
    ref_separate = "ref_separate" in request_json

    # for pattern in patterns:
    #     if pattern['pattern_type'] == 'reflective_based':
    #         reflection_pattern = ReflectivePattern()
    #     elif pattern['pattern_type'] == 'content_based':
    #         reflection_pattern = ContentbasePattern()
    #     else:
    #         # if unkonw pattern_type
    #         continue

    reflection_fields, data = Content_Pattern.get_field()
  

    for rf in reflection_fields:
        if request_json[rf] is None:
            request_json[rf] = ''

    ref_collection = {}
    for key, subkeys in data.items():
        ref_collection[key] = "\n".join([request_json[subkey] for subkey in subkeys])
    experience = ref_collection['experience']
    reflection = ref_collection['reflection']
    abstraction = ref_collection['abstraction']
    experiment = ref_collection["experiment"]


    logger.info("start processing")

    results = {}
    pattern_map =Content_Pattern.get_patternMap()
    principles = {}
    for p in patterns:
        original_pattern = p
        if p in pattern_map:
            original_pattern = pattern_map[p]
        # reflection_pattern = ContentbasePattern()
        if p in ["LPS", "BOA","SOA", "RRE"]:
            feedback = Content_Pattern.process_pattern(pattern_code = p, experience = experience, reflection = reflection, abstraction = abstraction, experimentation = experiment)
            if ref_separate:
                principles = add_separate_principle(p, feedback, principles)
        if p in ["BRN", "OAE","SRF", "TAN", "REN"]:
            feedback = Reflective_Pattern.process_pattern(pattern_code = p, experience = experience, reflection = reflection, abstraction = abstraction, experimentation = experiment)
            if ref_separate:
                principles = add_separate_principle(p, feedback, principles)
        if p not in ["LPS", "BOA", "SOA", "RRE", "BRN", "OAE", "SRF", "TAN", "REN"]:
            feedback = "this pattern is not available"
        if feedback is None:
            results[original_pattern] = "there's no sufficient data in this pattern."
            continue
        results[original_pattern] = feedback
    

    final_results = {
                "KOLBS": {
                    'feedback':results,
                },
                'user_id': user_id,
    }
    if principles != {}:
        final_results["KOLBS"]["principles"] = principles
    collectionName = 'reflection_feedback'
    if "request_type" in request_json and "user_stage" in request_json:
        final_results = {"KOLBS": {"feedback": results}, "user_stage": request_json["user_stage"], "request_type": request_json["request_type"], "user_id": user_id}
    save_to_firestore(final_results, reflection_job_id, collectionName)

    now = datetime.now(aest)
    end_time = now.strftime("%Y-%m-%d %H:%M:%S")

    try:
        update_reflection_query= {
            "reflection_job_id": reflection_job_id,
            "end_timestamp": end_time
            
        }
        reflectionJobs_update(engine, update_reflection_query)
    except Exception as e:
        logger.exception(e)
        return create_response("Unable to successfully Update Endtime of Reflection! Please check the application logs for more details.",
                               500,request.method
                               )
    
    collectionName = 'final_feedback'
    save_to_firestore(final_results, mainjob_id, collectionName)      
    component_list = ["KOLBS"]
    if "Mind-map-image-file" in request_json:
        for mm in request_json["Mind-map-image-file"]:
            file_name = mm.split('/')[-1]
            component_list.append(file_name)
    logger.warning(component_list)
    if "user_stage" in request_json:
        call_final_assessment(mainjob_id, user_id, component_list)
    logger.info(f"Reflection job {reflection_job_id} processing finishes!")
    return create_response('Reflection pipeline started',
                           200,
                           request.method, 
                           mainjob_id=reflection_job_id, 
                           user_id =user_id)

def save_to_firestore(data,docId,collection_name):
    try:
        # PROJECT environment variable is always in Terraform
        db_firestore = firestore.Client(project=os.getenv("PROJECT"))
        db_firestore.collection(collection_name).document(docId).set(data, merge=True)
    except Exception as e:
        print(e)
        return create_response('Failed to save result to Firesotre',
                           500,
                           request.method, 
                           )
# def create_response(message, subjob_id, user_id, code):
#     response = jsonify({'code': code, 'user_id': user_id, 'subjob_id': subjob_id,  'job_status': message})
#     response.headers.add("Access-Control-Allow-Origin", "*")
#     response.headers.add("Access-Control-Allow-Headers", "Content-Type")
#     response.headers.add("Access-Control-Allow-Methods", "GET,POST,DELETE")
#     return response

def call_final_assessment(mainjob_id, user_id, component_list):
    payload = {
        "mainjob-ID" : mainjob_id,
        "user_id" : user_id,
        "component_list": component_list
    }
    # FINAL_FEEDBACK_CLOUD_RUN_URL environment variable is always in Terraform
    final_url = os.getenv("FINAL_FEEDBACK_CLOUD_RUN_URL").replace('"', "").strip()
    # final_url = "https://ics-final-feedback-jjfeaywz4a-wl.a.run.app"
    final_id_token = generate_id_token(final_url)

    headers = {
                'Authorization': f'Bearer {final_id_token}',
                'Content-Type': 'application/json',
            }
    # Only activate the final feedback cloud run instance. So please dont handle the exception here
    try:
        requests.post(final_url, headers=headers, json=payload, timeout=3)
    except requests.exceptions.ReadTimeout as e:
        pass
    return


def generate_id_token(audience):
    google_request = google_requests.Request()
    credentials, _ = google.auth.default()
    token = id_token.fetch_id_token(google_request, audience)
    return token

# @app.errorhandler(405)
# def handle_method_not_allowed(e):
#     return jsonify({"error": "Method Not Allowed", "message": "Please use POST to request the API"}), 405


def add_separate_principle(pattern, feedback, principles):
    db_firestore = firestore.Client(project=os.getenv("PROJECT"))
    principle_collection = db_firestore.collection('principle_collection').document('collection').get().to_dict()
    for principle, details in principle_collection.items():
        for level, level_details in details.items():
            if "patterns" in level_details and "reflection" in level_details["patterns"] and pattern in level_details["patterns"]["reflection"]:
                if "final_score" in feedback and feedback["final_score"] > 0:
                    if principle not in principles:
                        principles[principle] = {"level": [level], "pattern": [pattern]}
                    else:
                        if level not in principles[principle]["level"]:
                            principles[principle]["level"].append(level)
                        if pattern not in principles[principle]["pattern"]:
                            principles[principle]["pattern"].append(pattern)
    
    return principles