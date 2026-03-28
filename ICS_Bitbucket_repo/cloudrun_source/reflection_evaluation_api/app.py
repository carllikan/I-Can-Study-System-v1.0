from flask import Flask, request, jsonify
from flask_utils import apply_security_headers
from google.cloud import tasks_v2
from gcp import *
from std_response import *
import os
import uuid
import json
from typing import Optional
import logging
app = Flask(__name__)
app.after_request(apply_security_headers)
@app.route('/', methods = ['POST'])
def main():
    logging.info(f"checking the method {request.method}")
    if request.method != 'POST':
        return create_response("Please use POST to request the API", 405,request.method)
    func_conf = gcp_get_config()
    request_json = request.get_json(silent=True)

    required_fields = [
        "mainjob-ID",
        "user_id",
        "patterns",
        "component_list",
        "reflection_id",
        "maineval-StartTime",
        "experiment",
        "abstraction_act",
        "abstraction_habits",
        "reflection_react",
        "reflection_struggle_triggers",
        "reflection_respond",
        "reflection_difficult",
        "reflection_feel_how",
        "reflection_sequence_events",
        "experience_gain",
        "experience_what",
        "experience_previous"

    ]
    for field in required_fields:
        # check whether required fields in request
        if field not in request_json:
            return create_response(f"Request must contain {field}", 400, request.method)


    reflection_queue = func_conf.get(
            "task_queue_reflection", "ReflectionQueue"
        )
    reflection_patterns = request_json["patterns"]
    start_time = request_json["maineval-StartTime"]
    mainjob_id = request_json["mainjob-ID"]
    reflection_job_id = str(uuid.uuid4())

    payload = {
            "reflection_job_id": reflection_job_id,
            "ref_separate": True,
            "mainjob-ID": mainjob_id,
            "maineval-StartTime": start_time,
            "user_id": request_json["user_id"],
            "patterns": reflection_patterns,
            "reflection_id": request_json["reflection_id"],
            "experience_previous": request_json[
                "experience_previous"
            ],
            "experience_what": request_json["experience_what"],
            "experience_gain": "This is the student's marginal gain look like:\n " + request_json["experience_gain"],
            "reflection_sequence_events": "The sequence of events, in chronological order:\n " + request_json[
                "reflection_sequence_events"
            ],
            "reflection_feel_how": "This is how the student felt during the experience:\n " + request_json[
                "reflection_feel_how"
            ],
            "reflection_difficult": "These is the parts of the experience the student felt went difficult and parts that they felt went well:\n " + request_json[
                "reflection_difficult"
            ],
            "reflection_respond": "This is how the student responded to difficulty:\n " + request_json[
                "reflection_respond"
            ],
            "reflection_struggle_triggers": "These are the triggers behind why the student responded a certain way:\n " + request_json[
                "reflection_struggle_triggers"
            ],
            "reflection_react": "This is why the student acted this way during the experience:\n " +  request_json[
                "reflection_react"
            ],
            "abstraction_habits": "These are the habits, beliefs, and tendencies that the student claims behind why the student acted the way they did:\n " + request_json[
                "abstraction_habits"
            ],
            "abstraction_act": "this is student's act and respond in similar ways of their life:\n " + request_json["abstraction_act"],
            "experiment": "This is the student think they can do next time:\n " + request_json["experiment"],
        }

    project_id = gcp_project_id()
    region = func_conf.get("region", "")
    project_number = gcp_project_number(project_id)
    ref_url = os.getenv("ICS_REFLECTION_EVALUATION_CLOUD_RUN_URL").replace('"', "").strip()
    create_http_task_with_token(
            project_id,
            region,
            reflection_queue,
            ref_url,
            json.dumps(payload).encode("utf-8"),
            f"{project_number}-compute@developer.gserviceaccount.com",
            ref_url,
        )
    return create_response("Reflection pipeline started", 200, request.method, subjob_id = reflection_job_id, user_id = request_json["user_id"])


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

# @app.errorhandler(405)
# def handle_method_not_allowed(e):
#     return jsonify({"error": "Method Not Allowed", "message": "Please use POST to request the API"}), 405
# @app.errorhandler(401)
# def unauthorized_error(error):
#     """
#     Handle 401 Unauthorized Error
#     :param error: Error object
#     :return: JSON response with error details
#     """
#     app.logger.warning(f"Unauthorized access attempt: {error}")
#     return create_response("Unauthorized access", 401)
# @app.errorhandler(403)
# def forbidden_error(error):
#     """
#     Handle 403 Forbidden Error
#     :param error: Error object
#     :return: JSON response with error details
#     """
#     app.logger.warning(f"Forbidden access attempt: {error}")
#     return create_response("Forbidden access", 403)
# @app.errorhandler(404)
# def not_found_error(error):
#     """
#     Handle 404 Not Found Error
#     :param error: Error object
#     :return: JSON response with error details
#     """
#     app.logger.warning(f"Resource not found: {error}")
#     return create_response("Resource not found", 404)
# @app.errorhandler(500)
# def internal_error(error):
#     """
#     Handle 500 Internal Server Error
#     :param error: Error object
#     :return: JSON response with error details
#     """
#     app.logger.error(f"Internal server error: {error}")
#     return create_response("Internal server error", 500)
# @app.errorhandler(400)
# def bad_request_error(error):
#     """
#     Handle 400 Bad Request Error
#     :param error: Error object
#     :return: JSON response with error details
#     """
#     app.logger.warning(f"Bad request: {error}")
#     return create_response("Bad request", 400)
