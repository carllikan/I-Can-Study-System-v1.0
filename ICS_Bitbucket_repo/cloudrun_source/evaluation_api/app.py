import os
import re
import uuid
from flask import Flask, request, jsonify
from flask_utils import apply_security_headers
from google.cloud import tasks_v2
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import google.auth
from gcp import *
from datetime import datetime
from dotenv import load_dotenv
import json
import logging
import pytz
from sql_orm import *
from std_response import *
from typing import Optional
from low_quality_checker import MindMapQualityChecker
from google.cloud import storage

load_dotenv()

app = Flask(__name__)
# Use the function with the after_request decorator
app.after_request(apply_security_headers)

@app.route("/", methods=["POST"])
def main():
    # if request.method != "POST":
    #     create_response("Please use POST to request the API", 405, request.method)
    
    # Fetch function configuration from gcp.py
    
    func_conf = gcp_get_config()
    # Initialize the logger
    logger = logging.getLogger()
    # Get the current time in the Australian Sydney time zone
    aest = pytz.timezone(func_conf.get("timezone", ""))
    now = datetime.now(aest)
    start_time = now.strftime("%Y-%m-%d %H:%M:%S")
    # Parse the JSON payload from the incoming request
    request_json = request.get_json(silent=True)


    if "track" in request_json:
        mainjob_id = request_json["mainjob_id"]
        if "mainjob_id" not in request_json or request_json["mainjob_id"] == "":
            return create_response(f"The Job you check is invalid", 400, request.method)
        
        engine = initial_engine()
        
        try:
            evalapi_query = {
                            "job_id":mainjob_id,
                            }
            
            
            result = evalApiJobs_query(engine, evalapi_query)

        except Exception as e:
            logger.exception(e)
            return create_response("Unable to successfully submit the eval_api_jobs\
                                    Please check the application logs for more details.", 500, request.method)
        
        if result.end_timestamp == result.start_timestamp:
            return create_response(f"{mainjob_id} is being processed", 200, request.method)
        else:
            return create_response(f"{mainjob_id} is finished", 200, request.method)
        
    # Define required fields for the request
    required_fields = [
        "request_id",
        "user_id",
        "user_stage",
        "request_type"
        # "feedback_what",
        # "guided_reflection",
        # "mindmap_files",
    ]
    stage_map = {
        "st-rapid-start": "RS",
        "st-fundamentals": "F1",
        "st-fundamentals-2": "F2",
        "st-briefing": "BR",
        "st-technique-training": "TT"
    }
    for field in required_fields:
        # check whether required fields in request
        if field not in request_json:
            return create_response(f"Request must contain {field}", 400, request.method)
        if request_json[field] == "":
            return create_response(f"{field} must not be empty", 400, request.method)
        # check whether required fields contain invalid symbols
        if field == "guided_reflection" or field == "mindmap_files":
            continue
        if not is_valid_input(request_json[field]):
            return create_response(f"{field} contains invalid characters.", 400, request.method)

    if request_json["user_stage"] not in stage_map:
        return create_response(f"user stage is not valid, please refer to evaluation api testing document https://addaxis.atlassian.net/wiki/spaces/IcanStudy/pages/1509752833/Evaluation+API+Testing", 400, request.method)
    # Fields required in the guided reflection section
    reflection_fields = [
        "reflection_id",
        "experience_previous",
        "experience_what",
        "experience_gain",
        "reflection_sequence_events",
        "reflection_feel_how",
        "reflection_difficult",
        "reflection_respond",
        "reflection_struggle_triggers",
        "reflection_react",
        "abstraction_habits",
        "abstraction_act",
        "experiment",
    ]
    reflection_need_process = False
    reflection_patterns = []
    mindmap_patterns = []
    # Process guided_reflection field if present
    
    pattern_map = {
        "reflection": {
            "enabling": {
                "RS": [
                    "BOA", "SOL", "SOA", "EUO", "ETG", "SBT", "SAP", "NMG", "TOA",
                    "RRE", "IOE", "RSL", "IAM", "TWP", "TOT", "RSG", "UPN", "UTG",
                    "IPN", "BTN",
                ],
                "F1": [
                    "BOA", "SOL", "SOA", "EUO", "ETG", "SBT", "SAP", "NMG", "TOA",
                    "RRE", "IOE", "RSL", "IAM", "TWP", "TOT", "RSG", "UPN", "UTG",
                    "IPN", "BTN",
                ],
                "F2": [],
                "BR": [
                    "SRN", "BRN", "TAN", "RAA", "REN", "EOD", "IES", "OAE", "NCK",
                    "BOA", "SOL", "SOA", "EUO", "ETG", "SBT", "SAP", "NMG", "TOA",
                    "RRE", "IOE", "RSL", "IAM", "TWP", "TOT", "RSG", "UPN", "UTG",
                    "IPN", "BTN",
                ],
                "TT": [
                    "SRN", "BRN", "TAN", "RAA", "REN", "EOD", "IES", "NCK", "BOA",
                    "SOL", "SOA", "EUO", "ETG", "SBT", "SAP", "NMG", "TOA", "RRE",
                    "IOE", "RSL", "IAM", "TWP", "TOT", "RSG", "UPN", "UTG", "IPN",
                    "BTN",
                ],
            },
            "learning": {
                "RS": [],
                "F1": ["SET", "RRE"],
                "F2": [
                    "SET", "RRE", "LPS", "TOA", "IOE", "RSL", "IAM", "TWP", "TOT",
                    "RSG", "UPN", "UTG", "IPN"
                ],
                "BR": [
                    "SET", "RRE", "LPS", "TOA", "IOE", "RSL", "IAM", "TWP", "TOT",
                    "RSG", "UPN", "UTG", "IPN", "SRN", "BRN", "TAN", "RAA", "REN",
                    "EOD", "IES", "OAE", "NCK", "ETG", "SBT", "SAP", "NMG"
                ],
                "TT": [
                    "SET", "RRE", "LPS", "TOA", "IOE", "RSL", "IAM", "TWP", "TOT",
                    "RSG", "UPN", "UTG", "IPN", "SRN", "BRN", "TAN", "RAA", "REN",
                    "EOD", "IES", "OAE", "NCK", "ETG", "SBT", "SAP", "NMG"
                ],
            }
        },
        "mindmap": {
            "enabling": {
                "RS": ["OSG", "MSG", "UTS"],
                "F1": ["OSG", "MSG", "UTS"],
                "F2": [],
                "BR": ["OSG", "MSG", "UTS"],
                "TT": ["OSG", "MSG", "UTS"],
            },
            "learning": {
                "RS": [],
                "F1": ["WFG", "ICG", "NSE"],
                "F2": ["WFG", "ICG", "TWY", "NSE", "ICO", "FOM", "SET"],
                "BR": ["WFG", "ICG", "TWY", "NSE", "ICO", "FOM", "SET"],
                "TT": [
                    "WFG", "ICG", "TWY", "UBE", "WAS", "SWG", "CGS", "QCD", "FOM", "CGG",
                    "ASW", "DSD", "ECD", "NSE", "ICO", "SET",
                ],
            }
        },
    }
    user_stage = stage_map[request_json["user_stage"]]
    if "guided_reflection" in request_json:
        for rf in reflection_fields:
            if rf not in request_json["guided_reflection"]:
                # return create_response(f"guided_reflection must contain {rf}", 400, request.method)
                pass
            if (
                rf in request_json["guided_reflection"]
                and request_json["guided_reflection"][rf] != ""
            ):
                reflection_need_process = True
        
        reflection_patterns = pattern_map["reflection"][request_json["request_type"]][user_stage]
        if reflection_patterns == None:
            return create_response("Stage is not valid", 400, request.method)
        reflection_exist = True
    else:
        reflection_exist = False
    # Process Mindmap pattern scaffolding if field mindmap_files present
    if "mindmap_files" in request_json:


        mindmap_patterns = pattern_map["mindmap"][request_json["request_type"]][user_stage]
        if mindmap_patterns == None:
            return create_response("Stage is not valid", 400, request.method)
        if len(request_json["mindmap_files"]) == 0:
            mindmap_exist = False
        else:
            mindmap_exist = True
    else:
        mindmap_exist = False

    if not mindmap_exist and not reflection_exist:
        return create_response("Reflection and Mindmap must not be empty", 400, request.method)
    

    # Generate the main job id
    mainjob_id = str(uuid.uuid4())
    # Connect to the MySQL database
    engine = initial_engine()
    try:
        evalapi_insert_query = {
                                "job_id":mainjob_id,
                                "start_timestamp":start_time,
                                "request":json.dumps(request_json),
                                }
        evalApiJobs_insert(engine, evalapi_insert_query)
        submission_jobs_insert_query={"job_id": mainjob_id,
                                        "learner_id": request_json.get("user_id", "")
                                        }
        submissionJobs_insert(engine, submission_jobs_insert_query)
    except Exception as e:
        logger.exception(e)
        return create_response("Unable to successfully submit the eval_api_jobs\
                                Please check the application logs for more details.", 500, request.method)
    
    project_id = gcp_project_id()
    region = func_conf.get("region", "")
    project_number = gcp_project_number(project_id)
    if len(reflection_patterns) > 0:
        payload = {
            "mainjob-ID": mainjob_id,
            "maineval-StartTime": start_time,
            "user_id": request_json["user_id"],
            "patterns": reflection_patterns,
            "reflection_id": request_json["guided_reflection"]["reflection_id"],
            "experience_previous": request_json["guided_reflection"][
                "experience_previous"
            ],
            "experience_what": request_json["guided_reflection"]["experience_what"],
            "experience_gain": request_json["guided_reflection"]["experience_gain"],
            "reflection_sequence_events": request_json["guided_reflection"][
                "reflection_sequence_events"
            ],
            "reflection_feel_how": request_json["guided_reflection"][
                "reflection_feel_how"
            ],
            "reflection_difficult": request_json["guided_reflection"][
                "reflection_difficult"
            ],
            "reflection_respond": request_json["guided_reflection"][
                "reflection_respond"
            ],
            "reflection_struggle_triggers": request_json["guided_reflection"][
                "reflection_struggle_triggers"
            ],
            "reflection_react": request_json["guided_reflection"][
                "reflection_react"
            ],
            "abstraction_habits": request_json["guided_reflection"][
                "abstraction_habits"
            ],
            "abstraction_act": request_json["guided_reflection"]["abstraction_act"],
            "experiment": request_json["guided_reflection"]["experiment"],
            "user_stage": request_json["user_stage"],
            "request_type": request_json["request_type"]
        }

        if len(mindmap_patterns) > 0 and mindmap_exist:
            payload["Mind-map-image-file"] = request_json["mindmap_files"]

        ref_url = os.getenv("REF_URL").replace('"', "").strip()
        reflection_queue = func_conf.get(
            "task_queue_reflection", "ReflectionQueue"
        )
        create_http_task_with_token(
            project_id,
            region,
            reflection_queue,
            ref_url,
            json.dumps(payload).encode("utf-8"),
            f"{project_number}-compute@developer.gserviceaccount.com",
            ref_url,
        )

    component_list = []
    if len(mindmap_patterns) > 0 and mindmap_exist:
        for mm in request_json["mindmap_files"]:
            file_name = mm.split("/")[-1]
            component_list.append(file_name)
        for i in range(len(request_json["mindmap_files"])):
            payload = {
                "mainjob-ID": mainjob_id,
                "maineval-StartTime": start_time,
                "user_id": request_json["user_id"],
                "user_stage": request_json["user_stage"],
                "request_type": request_json["request_type"],
                "patterns": mindmap_patterns,
                "mind-map-image-file": request_json["mindmap_files"][i],
                "component_list": component_list,
            }

            if len(reflection_patterns) > 0:
                payload["KOLBS"] = "True"

            file_path = request_json["mindmap_files"][i]
            bucket_name, file_name = file_path.replace('gs://', '').split('/', 1)
            print(bucket_name,file_name)
            # Check if the file exists in the bucket
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(file_name)

            if not blob.exists():
                logger.error(f"File {file_path} does not exist in bucket {bucket_name}")
                return create_response("This uploaded mind map does not exist in the bucket, please try again.", 404, request.method)
            
            
            logging.info("Start to precheck mind map quality.")
            
            mmp_quality_checker = MindMapQualityChecker(file_name,bucket_name)
            image_size = mmp_quality_checker.check_image_size()
            logging.info(f"checking image size {image_size}")
            mmp_background = mmp_quality_checker.check_white_background()
            logging.info(f'checking background:{mmp_background}')
            mmp_screenshot = mmp_quality_checker.check_if_screenshot()
            logging.info(f'checking screenshot:{mmp_screenshot}')
            mmp_quality = mmp_quality_checker.check_mind_map_quality()
            logging.info(f'checking mmp_quality:{mmp_quality}')
            checker_response = mmp_quality_checker.check_mind_map_quality()
            logging.info(f"checking the checker response: {checker_response}")

            
            if checker_response is not True:
                logging.info(f"The mind map {file_name} quality is bad!")
                return create_response(f"The mind map {file_name} quality is bad!", 400, request.method)
                

            mm_url = os.getenv("MM_URL").replace('"', "").strip()
            mindmap_queue = func_conf.get("task_queue_mindmap", "MindMapQueue")
            create_http_task_with_token(
                project_id,
                region,
                mindmap_queue,
                mm_url,
                json.dumps(payload).encode("utf-8"),
                f"{project_number}-compute@developer.gserviceaccount.com",
                mm_url,
            )

    return create_response("Job Started", 200, request.method, mainjob_id = mainjob_id, request_id = request_json["request_id"], user_id = request_json["user_id"])


def is_valid_input(value):
    # This pattern ensures the value contains characters typically allowed in URLs and text.
    # Alphanumeric characters, hyphens, underscores, periods, and tildes are considered valid.
    pattern = re.compile("^[a-zA-Z0-9-_.~]+$")
    return bool(pattern.match(value))


def generate_id_token(audience):
    google_request = google_requests.Request()
    credentials, _ = google.auth.default()
    token = id_token.fetch_id_token(google_request, audience)
    return token


def create_http_task_with_token(
    project: str,
    location: str,
    queue: str,
    url: str,
    payload: bytes,
    service_account_email: str,
    audience: Optional[str] = None,
) -> tasks_v2.Task:
    """Create an HTTP POST task with an OIDC token and an arbitrary payload.
    Args:
        project: The project ID where the queue is located.
        location: The location where the queue is located.
        queue: The ID of the queue to add the task to.
        url: The target URL of the task.
        payload: The payload to send.
        service_account_email: The service account to use for generating the OIDC token.
        audience: Audience to use when generating the OIDC token.
    Returns:
        The newly created task.
    """

    # Create a client.
    client = tasks_v2.CloudTasksClient()

    # Construct the request body.
    task = tasks_v2.Task(
        http_request=tasks_v2.HttpRequest(
            http_method=tasks_v2.HttpMethod.POST,
            url=url,
            oidc_token=tasks_v2.OidcToken(
                service_account_email=service_account_email,
                audience=audience,
            ),
            body=payload,
            headers={"Content-type": "application/json"},
        ),
    )

    # Use the client to build and send the task.
    return client.create_task(
        tasks_v2.CreateTaskRequest(
            parent=client.queue_path(project, location, queue),
            task=task,
        )
    )


# @app.route("/track", methods=["POST"])
# def main_check():
#     request_json = request.get_json(silent=True)
#     mainjob_id = request_json["mainjob_id"]
#     if "mainjob_id" not in request_json or request_json["mainjob_id"] == "":
#         return create_response(f"The Job you check is invalid", 400, request.method)
    
#     engine = initial_engine()
    
#     try:
#         evalapi_query = {
#                                 "job_id":mainjob_id,
#                                 }
        
        
#         result = evalApiJobs_query(engine, evalapi_query)

#     except Exception as e:
#         logger.exception(e)
#         return create_response("Unable to successfully submit the eval_api_jobs\
#                                 Please check the application logs for more details.", 500, request.method)
    
#     if result.end_timestamp == "":
#         return create_response(f"{mainjob_id} is being processed", 200, request.method)
#     else:
#         return create_response(f"{mainjob_id} is finished", 200, request.method)