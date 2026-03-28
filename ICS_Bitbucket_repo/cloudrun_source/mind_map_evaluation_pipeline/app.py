import base64
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, Response, jsonify
from flask_utils import apply_security_headers
from google.cloud import firestore
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import google
from pipeline_alternative_v8 import GraphFeatureExtractionPipeline
from check_patterns import DetectPatterns
from sql_orm import *
import json
import logging
import pytz
import requests
import uuid
import os
from std_response import *
from ultralytics import YOLO
from gcp import *
from google.cloud import storage
import tempfile
PROJECT = gcp_project_id()
# project_number = gcp_project_number(PROJECT)
# func_conf = gcp_get_config()
# HF_ACCESS_TOKEN = gcp_get_secret(project_number,func_conf.get('hf_access_token', 'hf_access_token_name' ))
app = Flask(__name__)
app.after_request(apply_security_headers)
load_dotenv()
logger = gcp_logger()
aest = pytz.timezone("Australia/Sydney")


model = None  # Global variable to hold the YOLO model
model_loaded = False  # Flag to ensure model is loaded only once

@app.before_request
def load_yolo_model():
    global model, model_loaded
    if not model_loaded:
    # model_name = 'models_yolov9_tail.pt'
        model_name = "yolov9_tail.pt"
        bucket_name = f"{PROJECT}-yolo-checkpoints"
        model_path = f"models/{model_name}"
        logger.info(f"checking {bucket_name}, {model_path}")
    
        try:
            # Initialize GCS client and download the model to a temporary file
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(model_path)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_model_path = os.path.join(temp_dir, model_name)
                logger.info(f"checking temp path {temp_model_path}")
                blob.download_to_filename(temp_model_path)

                # Debug: Check if the file exists and its size
                logger.info("checking file path and size")
                if os.path.exists(temp_model_path):
                    logger.info(f"Temporary model file size: {os.path.getsize(temp_model_path)} bytes")
                    print(f"Temporary model file size: {os.path.getsize(temp_model_path)} bytes")

                # Load the model from the temporary file
                model = YOLO(temp_model_path)
                model_loaded = True
                logger.info("YOLO model loaded successfully from GCS")
 
            model_loaded = True
        except Exception as e:
            logger.exception("Failed to load YOLO model from GCS")
            raise e  # Re-raise exception for debugging
        
@app.route("/", methods=["POST"])
def Mindmap_Evaluation_Pipeline():
    PROJECT = os.getenv("PROJECT")
    db_firestore = firestore.Client(PROJECT)
    now = datetime.now(aest)
    start_time = now.strftime("%Y-%m-%d %H:%M:%S")
    request_json = request.get_json()
    if "message" in request_json:
        pubsub_message = request_json["message"]
        pubsub_message_decode = base64.b64decode(pubsub_message["data"]).decode("utf-8")
        request_json = json.loads(pubsub_message_decode)
    user_id = request_json.get("user_id", "")
    file_path = request_json.get("mind-map-image-file", "")
    bucket_name = file_path.split("/")[2]
    
    file_name = file_path.split("/")[-1]
    mainjob_id = request_json.get("mainjob-ID", "")
    if "mindmap_job_id" in request_json:
        mindmap_job_id = request_json["mindmap_job_id"]
    else:
        mindmap_job_id = str(uuid.uuid4())

    logger.info(f"mindmap job id is {mindmap_job_id}")
    logging.info(f"mindmap job id is {mindmap_job_id}")
    engine = initial_engine()
    try:
        component_insert_query = {"job_id":mainjob_id,
                                  "sub_component_type":"Mindmap",
                                  "sub_component_job_id":mindmap_job_id}
        
        evalApiComponentJobs_insert(engine, component_insert_query)
        eval_jobs_insert_query={"mindmap_job_id": mindmap_job_id,
                                "eval_job_id": mainjob_id,
                                "start_timestamp": start_time,
                                "request": json.dumps(request_json)

        }
        mindmapJobs_insert(engine, eval_jobs_insert_query)
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="Unable to successfully Add to eval_api_component_jobs and Mindmap_jobs! Please check the "
            "application logs for more details.",
        )

    pipeline = GraphFeatureExtractionPipeline(image_file_path=file_path,
                                              model = model
                                              )
    nodes_df, edges_df,message= pipeline.extract_feature()
    graph_features = pipeline.generate_json_output(nodes_df, 
                                                   edges_df, 
                                                    file_name, 
                                                    user_id,
                                                    message
                                                    )
    logger.info("Features extraction finishes!")
    
    logger.info("Start saving the results to firestore.")

    collection_name = "ics-mind-maps-features"
    save_to_firestore(graph_features, mindmap_job_id, collection_name)
    logger.info("The features have been succesffully saved to firestore!")

    logger.info("Start to evaluate the mind map!")
    pattern_list = request_json.get("patterns", [])
    pattern_name_id_map =  db_firestore.collection('pattern_id_name_map').document('mapping').get().to_dict()
    pattern_id_name_map = {v: k for k, v in pattern_name_id_map.items()}

    pattern_name_list = [pattern_id_name_map[pattern] for pattern in pattern_list if pattern in pattern_id_name_map] 
    # filtered_patterns = pattern_list

    detect_patterns_instance = DetectPatterns(graph_features['graph'],
                                              bucket_name,
                                              file_name
                                            )
                     
    patterns_evaluation = detect_patterns_instance.detect_patterns()
    try:
        patterns_evaluation = json.loads(patterns_evaluation)
    except:
        logger.info("json parse failed")
        logger.info(patterns_evaluation)

    patterns_evaluation = {k: patterns_evaluation[k] for k in pattern_name_list if k in patterns_evaluation}
    logger.info("Mind map evaluation finishes!")

    logger.info("Start to save evaluation to firestore.")
    evaluations = {"feedback": patterns_evaluation, "user_id": user_id}
    collection_name = "ics-mind-maps-feedback"
    save_to_firestore(evaluations, mindmap_job_id, collection_name)
    final_result = {file_name: {"evaluation": patterns_evaluation}, "user_id": user_id}
    if "request_type" in request_json and "user_stage" in request_json:
        final_result = {file_name: {"evaluation": patterns_evaluation}, "user_stage": request_json["user_stage"], "request_type": request_json["request_type"], "user_id": user_id}
    save_to_firestore(final_result, mainjob_id, "final_feedback")

    now = datetime.now(aest)
    end_time = now.strftime("%Y-%m-%d %H:%M:%S")

    try:
        update_mindmap_query= {
            "mindmap_job_id": mindmap_job_id,
            "end_timestamp": end_time
            
        }
        mindmapJobs_update(engine, update_mindmap_query)
    except Exception as e:
        logger.exception(e)
    logger.info("The evaluations have been succesffully saved to firestore!")
    # Calculate the elapsed time

    component_list = request_json["component_list"]
    if "KOLBS" in request_json:
        component_list.append("KOLBS")
    logger.warning(component_list)
    if "user_stage" in request_json:
        call_final_assessment(mainjob_id, user_id, component_list)

    logger.info(f"Mindmap job {mindmap_job_id} processing finishes!")
    return create_response("Mindmap pipeline finished",200,request.method,subjob_id= mindmap_job_id, user_id=user_id)


def save_to_firestore(data, docId, collection_name):
    try:
        PROJECT = os.getenv("PROJECT")
        db = firestore.Client(project=PROJECT)
        docInfo = data
        db.collection(collection_name).document(docId).set(docInfo, merge=True)
    except Exception as e:
        logger.exception(e)


def call_final_assessment(mainjob_id, user_id, component_list):
    payload = {
        "mainjob-ID": mainjob_id,
        "user_id": user_id,
        "component_list": component_list
    }
    final_url = os.getenv("FINAL_FEEDBACK_CLOUD_RUN_URL").replace('"', "").strip()
    # final_url = "https://ics-final-feedback-nv2ytaumqa-wl.a.run.app"
    final_id_token = generate_id_token(final_url)

    headers = {
        "Authorization": f"Bearer {final_id_token}",
        "Content-Type": "application/json",
    }
    try:
        requests.post(final_url, headers=headers, json=payload, timeout=3)
    except requests.exceptions.ReadTimeout:
        pass
    return

# AIzaSyCuaU76AVMzmQ-AYQ9os6Hrn-UyeANhd3k
def generate_id_token(audience):
    google_request = google_requests.Request()
    credentials, _ = google.auth.default()
    token = id_token.fetch_id_token(google_request, audience)
    return token